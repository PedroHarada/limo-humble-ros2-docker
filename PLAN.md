# Preparar ambiente para FAST_LIO + Nav2 (RRT/A*) no mundo floresta

## Contexto

Na Reunião 03 (2026-09-18) ficou definido testar um fluxo de navegação
LiDAR → FAST_LIO → Nav2 → movimento do LIMO, comparando planners RRT e A*,
validado no mundo de floresta. O usuário já tem (ou vai ter) os componentes
"de algoritmo": o FAST_LIO vem de um colega (ainda não está nesta máquina), os
planners RRT/A* ele mesmo vai escrever, e o world de teste (`FOREST_WORLDS.zip`,
já descompactado em `FOREST_WORLDS/` na raiz do repo) também já está pronto.

O pedido aqui é só **infraestrutura**: deixar o Docker/workspace prontos para
receber e rodar essas peças, sem implementar os algoritmos nem desenhar o
mundo — consistente com o papel que o usuário já pede neste projeto (ele
escreve os algoritmos, a infra é construída à parte).

Investigação confirmou três descasamentos entre o que existe hoje e o que o
fluxo pretendido precisa:

- O LiDAR simulado do LIMO é 2D (`sensor_msgs/LaserScan`, plano único, ver
  `limo_gazebo.gazebo` / `limo_four_diff.xacro`). FAST_LIO precisa de nuvem 3D.
  Decisão do usuário: **precisa ser compatível com o Livox Mid-360**.
- O Nav2 hoje localiza com **AMCL contra mapa estático** salvo pelo
  `slam_toolbox` (`ws/src/limo_nav2/config/nav2_params.yaml`). O fluxo novo
  quer que o FAST_LIO construa o frame do mundo — ou seja, tira o AMCL do
  caminho.
- O world `forest_diverse_10min.sdf` referencia `model://mrs_gazebo_common_resources`,
  que não está em `FOREST_WORLDS/` nem no repo. Decisão do usuário: **clonar
  esse repositório no `setup.sh`**, do mesmo jeito que `limo_ros2` já é clonado.

## O que já está pronto (não mexer)

- Nav2 bringup funcional (`ws/src/limo_nav2/launch/nav2.launch.py`,
  `config/nav2_params.yaml`) com `RegulatedPurePursuitController` ajustado
  para Ackermann.
- `/goal_pose` via `ros2 topic pub` **já funciona sem mudança nenhuma** — o
  `bt_navigator` do Nav2 escuta esse tópico por padrão e dispara
  `NavigateToPose` internamente. Não precisa de código novo para isso.
- Mundo dinâmico existente (`limo_worlds/worlds/dynamic_world.model` +
  `obstacle_mover`) serve de padrão para o launch do mundo floresta.
- Docker com `osrf/ros:humble-desktop-full`, Nav2, slam_toolbox e Gazebo
  Classic já instalados (`Dockerfile`).

## Escopo do trabalho (5 frentes)

### 1. Sensor 3D — Livox Mid-360 simulado

- Adicionar o pacote `livox_laser_simulation` (plugin Gazebo Classic com
  padrão de varredura não-repetitivo do Mid-360) ao workspace, clonado no
  `setup.sh` como já é feito com `limo_ros2`.
- Editar `ws/src/limo_ros2/limo_car/gazebo/{ackermann_with_sensor,sensor}.xacro`
  para adicionar o link/sensor Mid-360 com o plugin, publicando `PointCloud2`
  (ou `livox_ros_driver2/CustomMsg`, conforme o que o `livox_laser_simulation`
  suportar) em um tópico novo, ex. `/livox/lidar`. É o modelo Ackermann, não o
  `limo_four_diff.xacro` (diff-drive) — o Nav2 e o resto do projeto usam o
  Ackermann, então é ali que o sensor precisa existir.
- **Não remover** o laser 2D existente (`/limo/scan` / `/scan`) — o Nav2
  continua usando ele para os costmaps.
- Aplicar como patch em `patches/` (seguindo o padrão de
  `limo_ros2-fixes.patch`), já que `limo_ros2` é clonado, não versionado.

### 2. Dependências de build do FAST_LIO no Docker

- No `Dockerfile`, adicionar as dependências que o FAST_LIO exige:
  `libpcl-dev`, `libeigen3-dev`, `libgoogle-glog-dev` e build from source do
  `Sophus` (não tem pacote apt no Humble) e do `livox_ros_driver2` (clonado
  no `setup.sh`, branch `humble`).
- Deixar `ws/src/FAST_LIO` e `ws/src/livox_ros_driver2` como diretórios que o
  `colcon build` do workspace já cobre assim que o código for colocado lá —
  não clonar o FAST_LIO em si (o usuário ainda não tem acesso ao repositório
  do colega).
- Documentar no README o passo manual: "coloque o FAST_LIO em `ws/src/FAST_LIO`
  e rode `colcon build --packages-select fast_lio`".

### 3. Nav2 sem AMCL — consumir a saída do FAST_LIO

- Em `ws/src/limo_nav2/launch/nav2.launch.py`, adicionar um argumento (ex.
  `localization_source:=fast_lio|amcl`, default a decidir) que:
  - com `amcl`: comportamento atual, inalterado;
  - com `fast_lio`: não sobe `amcl`, e usa a odometria/tf publicada pelo
    FAST_LIO para a cadeia `map` → `odom` → `base_footprint`.
- Como o formato exato dos tópicos/frames do FAST_LIO só se confirma quando o
  código chegar (tipicamente publica odometria em `/Odometry` e tf
  `camera_init` → `body`), deixar isso como **parâmetros de remapeamento**
  documentados em vez de hardcoded, e marcar no README como pendência a
  validar assim que o pacote do colega chegar.
- Ajustar `nav2_params.yaml`: `global_costmap`/`local_costmap` continuam
  usando o laser 2D (`scan`) para obstáculos — FAST_LIO entra só como fonte
  de localização/frame, não substitui o costmap 2D.

### 4. Esqueleto de planners Nav2 (A* e RRT)

- Novo pacote `ws/src/limo_nav2_planners` (C++), com:
  - `AStarPlanner` e `RRTPlanner`, cada um implementando a interface
    `nav2_core::GlobalPlanner` (métodos `configure`, `cleanup`, `activate`,
    `deactivate`, `createPlan`) com corpo mínimo/placeholder para o usuário
    preencher.
  - `plugin.xml` registrando as duas classes via `pluginlib`.
- Em `ws/src/limo_nav2/config/nav2_params.yaml`, ampliar
  `planner_server.planner_plugins` para incluir as duas novas opções ao lado
  do `GridBased` (NavFn) existente, permitindo trocar de planner por
  parâmetro sem recompilar o Nav2.

### 5. Mundo floresta

- Mover o conteúdo de `FOREST_WORLDS/` (world `forest_diverse_10min.sdf` +
  `models/`, ~307 MB) para dentro do workspace, em
  `ws/src/limo_worlds/worlds/` e `ws/src/limo_worlds/models/` (mesmo pacote
  do mundo dinâmico existente).
- Criar um launch novo (`forest_world.launch.py`, no padrão de
  `dynamic_obstacles.launch.py` / `ackermann_gazebo.launch.py world:=...`)
  que sobe o Gazebo com esse world e faz spawn do LIMO nele.
- No `setup.sh`, clonar `mrs_gazebo_common_resources` (mesmo padrão do clone
  de `limo_ros2`). A variável `GAZEBO_MODEL_PATH` (incluindo esse diretório e
  `models/forest-gen-models/`) é montada em `forest_world.launch.py` via
  `SetEnvironmentVariable`, não no `setup.sh` — evita depender do usuário ter
  re-sourced o shell, e resolve o `model://mrs_gazebo_common_resources`
  referenciado pelo world.
- Remover o resíduo `models/world_jean_tree/model.sdf.bak` ao copiar (não é
  usado, só lixo do zip).

## Fora de escopo (deliberadamente)

- Implementar a lógica de RRT/A* dentro dos plugins — só o esqueleto.
- Trazer o código do FAST_LIO em si — só as dependências de build.
- Desenhar/editar o mundo floresta — só integrá-lo ao workspace.

## Verificação

1. `docker compose build` conclui sem erro com as novas dependências.
2. `colcon build` do workspace compila `limo_nav2_planners` e (se o FAST_LIO
   já tiver sido colocado em `ws/src/FAST_LIO`) o pacote do colega.
3. Subir `forest_world.launch.py`: Gazebo abre o mundo floresta com o LIMO
   spawnado, sem erros de `model://` faltando no log.
4. Confirmar que `/livox/lidar` publica `PointCloud2`/`CustomMsg` com
   `ros2 topic echo` enquanto o Gazebo roda.
5. Subir `nav2.launch.py localization_source:=amcl` (regressão: fluxo antigo
   continua funcionando).
6. Enviar `ros2 topic pub /goal_pose geometry_msgs/PoseStamped "{...}"` e
   confirmar no RViz que o Nav2 recebe o goal e tenta planejar com o
   `GridBased` (NavFn) — antes de qualquer planner novo estar implementado,
   isso já deve funcionar hoje.
