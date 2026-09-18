# Como ROS 2, Gazebo e Nav2 se comunicam neste ambiente

Este documento explica o mecanismo de comunicação entre ROS 2, Gazebo Classic
e Nav2 **especificamente como estão configurados neste repositório**. Para o
"o que foi feito e por quê" de todo o ambiente, veja o [README.md](README.md);
para operação do dia a dia, veja o [GUIA-BASIC.md](GUIA-BASIC.md).

**Atualização:** o pacote `limo_nav2` já existe e está validado (ver
README.md, Parte 4) — a seção 4 abaixo, que descrevia como o Nav2 "vai se
encaixar", já reflete a implementação real, não mais uma projeção.

---

## 1. A camada de transporte: DDS, não um `roscore`

Diferente do ROS 1, o ROS 2 não tem um processo central de registro de nós.
Cada nó fala diretamente com os outros via **DDS** (Data Distribution
Service), o middleware de publish/subscribe que o ROS 2 usa por baixo dos
panos (aqui, a implementação padrão do Humble, `rmw_fastrtps_cpp`). Os nós se
descobrem automaticamente na rede por multicast UDP — não existe um broker.

Isso tem duas consequências diretas para este ambiente:

- **`network_mode: host` no `docker-compose.yml`**: o container não tem sua
  própria interface de rede isolada. Ele usa a pilha de rede do host
  diretamente, o que evita ter que configurar NAT ou portas para o descoberta
  multicast do DDS atravessar a fronteira do container.
- **`ROS_DOMAIN_ID: 42`**: como o container compartilha a rede do host (que
  também tem outro container ROS 2 rodando, ver README.md), o domínio DDS é o
  único mecanismo que impede um nó de um container "ouvir" o outro. Nós só se
  descobrem dentro do mesmo `ROS_DOMAIN_ID`.

Todo o resto deste documento — tópicos, TF, `/clock` — viaja sobre esse
transporte DDS.

## 2. Gazebo dentro do grafo ROS 2

O Gazebo Classic (`gzserver` + `gzclient`) **não é, em si, um nó ROS 2**: é um
simulador de física independente. A ponte é o pacote `gazebo_ros`, que carrega
**plugins** dentro do processo do `gzserver`. Cada plugin roda como parte do
Gazebo, mas usa a API do `rclcpp` para publicar e assinar tópicos no mesmo
grafo DDS que qualquer outro nó ROS 2 — para o resto do sistema, é
indistinguível de um nó "normal".

### 2.1 O launch que sobe tudo

`ros2 launch limo_car ackermann_gazebo.launch.py` inclui, em sequência:

1. **`ackermann.launch.py`** → sobe o `robot_state_publisher`, que processa o
   XACRO (`ackermann_with_sensor.xacro`) em URDF e publica esse URDF no
   parâmetro/tópico `/robot_description`. Esse nó também escuta `/joint_states`
   e publica a parte fixa da árvore TF (`base_footprint → base_link →
   laser_link, depth_camera_link, imu_link` etc.).
2. **`gazebo_ros/launch/gazebo.launch.py`** → sobe o `gzserver` (física) e o
   `gzclient` (janela 3D), carregando o mundo `worlds/empty_world.model`.
3. **`spawn_entity.py`** (nó do pacote `gazebo_ros`) → lê o tópico
   `robot_description` e pede ao `gzserver`, via seu serviço interno, para
   instanciar o robô na simulação. É o elo entre "URDF publicado por um nó
   ROS 2" e "entidade física dentro do Gazebo".
4. **`rviz2`** → assina os tópicos publicados pelos plugins abaixo para
   desenhar o robô, o laser e a câmera.

### 2.2 Os plugins e o que cada um publica/assina

Cada plugin é declarado dentro do XACRO/URDF, em blocos `<gazebo>`, e vira
parte do binário do `gzserver` quando o robô é spawnado:

| Plugin (`.so`) | Papel | Tópicos ROS 2 |
|---|---|---|
| `libgazebo_ros_ackermann_drive.so` | controlador de tração e direção Ackermann | assina `/cmd_vel` (`geometry_msgs/Twist`); publica `/odom` (`nav_msgs/Odometry`) e o TF `odom → base_footprint` |
| `libgazebo_ros_ray_sensor.so` | lidar 2D | publica `/scan` (`sensor_msgs/LaserScan`), remapeado de `~/out` |
| `libgazebo_ros_camera.so` | câmera de profundidade | publica `/depth_camera/rgb/image_raw`, `/depth_camera/depth/image_raw`, `camera_info`, `points` (nuvem de pontos) |
| `libgazebo_ros_imu_sensor.so` | IMU | publica `/limo/imu` (`sensor_msgs/Imu`) |

Todos esses tópicos existem porque o Gazebo os publica **como se fosse** um
nó ROS 2 comum — quem envia `Twist` em `/cmd_vel` (o `rqt_robot_steering` ou o
`teleop_twist_keyboard`) não sabe, e não precisa saber, que do outro lado
existe um simulador de física em vez de motores reais.

### 2.3 O relógio: `use_sim_time` e `/clock`

O `gzserver` publica `/clock` (`rosgraph_msgs/Clock`) com o tempo simulado.
Todo nó que precisa de timestamps coerentes com essa simulação — o
`robot_state_publisher`, o `slam_toolbox`, e futuramente o Nav2 — recebe o
parâmetro `use_sim_time: true` para consultar `/clock` em vez do relógio de
parede do sistema. Sem essa coerência, TF e mensagens com timestamp
"futuro" ou "passado" em relação ao simulador seriam descartados por
tolerância de tempo — é o item mais citado na tabela de troubleshooting do
`GUIA-BASIC.md`.

### 2.4 TF: as duas árvores que se encontram

Há duas fontes de TF independentes, que precisam compartilhar um frame comum
para formar uma árvore só (ver README.md, correção nº 7, para o bug real que
isso causou aqui):

- `robot_state_publisher` publica os frames **fixos** do URDF a partir de
  `base_link` (sensores).
- `libgazebo_ros_ackermann_drive.so` publica a odometria a partir de
  `base_footprint` (pose do robô no mundo) e os joints das rodas.

`base_footprint → base_link` é o elo fixo que junta as duas. Sem ele, como
documentado no README, RViz, SLAM e (no futuro) o Nav2 veem duas árvores TF
desconexas e nada funciona, mesmo com todos os tópicos publicando
normalmente.

## 3. SLAM: o elo que hoje faz o papel de "quase-Nav2"

O `limo_slam` (pacote próprio deste repositório, não do upstream) mostra o
mesmo padrão de comunicação que o Nav2 vai usar: um nó ROS 2 comum,
consumindo os mesmos tópicos que o Gazebo publica, sem qualquer acoplamento
direto ao simulador.

```
gzserver (plugins) --/scan--------> slam_toolbox --/map------> RViz
                    --/tf (odom→base_footprint)--^
                    --/clock (use_sim_time)-------^
```

O `slam_toolbox` (`async_slam_toolbox_node`) assina `/scan` e `/tf`, e publica:

- `/map` (`nav_msgs/OccupancyGrid`), a grade de ocupação.
- o elo de TF `map → odom`, que fecha a árvore completa
  `map → odom → base_footprint → base_link → sensores`.

Esse elo `map → odom` é exatamente o que o Nav2 vai precisar para localizar o
robô dentro de um mapa — hoje é o `slam_toolbox` que o fornece; quando o Nav2
entrar em cena com um mapa salvo, será o `amcl` a publicá-lo.

## 4. Nav2: como se encaixa (pacote `limo_nav2`)

O Nav2 é um **conjunto de nós ROS 2 comuns** — não tem relação direta com o
Gazebo. Ele não sabe se `/scan` e `/odom` vêm de um simulador ou de um robô
físico: só assina tópicos e publica tópicos, exatamente como o `slam_toolbox`
faz hoje. É por isso que o Nav2 "simplesmente funciona" sobre uma simulação
Gazebo — ele está a duas camadas de distância do simulador, falando somente
com o grafo ROS 2.

A arquitetura típica do Nav2, aplicada aos tópicos que **já existem** neste
ambiente, seria:

```
                         mapa salvo (sala.yaml/.pgm)
                                   |
                                   v
gzserver --/scan---------------> amcl --/tf (map→odom)---+
gzserver --/odom, /tf-----------> ├─────────────────────>│
                                   |                       v
                          nav2_costmap_2d (local+global) --> planner_server
                                   |                              |
                                   v                              v
                          controller_server <---- caminho global--┘
                                   |
                                   v
                              /cmd_vel  --------------> libgazebo_ros_ackermann_drive.so
```

Papel de cada peça, em termos de comunicação ROS 2 (a implementação real está
em `ws/src/limo_nav2/`, documentada com as decisões técnicas no README.md,
Parte 4):

- **`map_server`**: carrega o `.yaml`/`.pgm` salvo com
  `nav2_map_server map_saver_cli` (ver GUIA-BASIC.md, seção 6) e publica
  `/map` como um tópico latched (`nav_msgs/OccupancyGrid`), da mesma forma que
  o `slam_toolbox` publica hoje — mas a partir de um arquivo, não de scans em
  tempo real.
- **`amcl`**: assina `/scan`, `/map` e `/tf`, e publica o elo `map → odom`
  via TF — a mesma função que o `slam_toolbox` cumpre agora, só que por
  localização probabilística (partículas) contra um mapa fixo, em vez de
  construir o mapa.
- **`nav2_costmap_2d` (local e global)**: assina `/scan` (ou nuvem de pontos
  da câmera de profundidade, se configurado) e o `/map`, para inflar
  obstáculos em torno das paredes e objetos.
- **`planner_server`** e **`controller_server`**: o par que planeja a rota
  global e depois a segue localmente, publicando comandos de velocidade em
  `/cmd_vel` — o **mesmo tópico** que hoje é publicado manualmente pelo
  `rqt_robot_steering` ou `teleop_twist_keyboard`. Do ponto de vista do
  `libgazebo_ros_ackermann_drive.so`, não há diferença entre um humano
  movendo um slider e o Nav2 decidindo a velocidade — ambos só publicam
  `geometry_msgs/Twist` no mesmo tópico.
- **`bt_navigator`**: orquestra os nós acima via uma árvore de comportamento
  (Behavior Tree), exposta como uma ação ROS 2 (`NavigateToPose`), que é o que
  um cliente (RViz com a ferramenta "Nav2 Goal", ou um script) chama para
  mandar o robô a um destino.

### 4.1 A complicação específica deste robô: cinemática Ackermann

O Nav2 assume, por padrão, um robô de tração diferencial (o `controller_server`
padrão gira o robô no lugar para se alinhar ao caminho). O LIMO simulado aqui
usa `libgazebo_ros_ackermann_drive.so`: como o `GUIA-BASIC.md` documenta na
seção "Particularidade do ackermann", **girar sem velocidade linear não move o
robô**. Isso não é um problema de comunicação — os tópicos e mensagens são os
mesmos — mas exige troca do plugin de controle do Nav2 (por exemplo, um
`RegulatedPurePursuitController` com restrição de curvatura mínima, em vez do
`DWB` padrão) para gerar comandos de `/cmd_vel` compatíveis com a cinemática
real do robô — exatamente o que o `limo_nav2` faz (README.md, Parte 4), com
`min_turning_radius` calculado a partir do `wheelbase` e do `max_steer` reais
do robô.

## 5. Resumo do fluxo de mensagens (estado atual do repositório)

```
              use_sim_time=true, /clock
                       |
   +-------------------+-------------------+
   |                                       |
   v                                       v
gzserver (plugins Gazebo)  <----/cmd_vel---+---- rqt_robot_steering /
   |   |   |                                     teleop_twist_keyboard
   |   |   +--/limo/imu------------------> (não consumido hoje)
   |   +--/depth_camera/*----------------> RViz
   +--/scan---------------+---------------> RViz
   |                      |
   +--/odom, /tf----------+
                           v
                    slam_toolbox --/map, tf(map→odom)--> RViz (slam.rviz)
```

O Nav2 se insere **no mesmo ponto** onde o `slam_toolbox` está durante o
mapeamento (consumindo `/scan`, `/odom`, `/tf`) e devolve `/cmd_vel` no lugar
do teleop — sem exigir nenhuma mudança na parte que já funciona (Gazebo,
plugins, TF). Os dois não rodam ao mesmo tempo: o `slam_toolbox` é usado para
gerar o mapa (`limo_slam`), e o Nav2 (`limo_nav2`) depois localiza contra esse
mapa já salvo.

---

*Este documento descreve o comportamento observado e validado em todo o
ambiente: Gazebo, SLAM (`limo_slam`) e Nav2 (`limo_nav2`, README.md Parte 4).*
