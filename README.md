# LIMO (AgileX) — simulação em Docker

*[English version](README.en.md)*

Ambiente de simulação do robô LIMO com **ROS 2 Humble**, **Gazebo Classic** e
**Nav2**, isolado em um container Docker, com aceleração gráfica pela GPU
integrada (Mesa).

Este documento registra **o que foi feito, como e por quê**. Para operar o
ambiente no dia a dia, veja o [GUIA-BASIC.md](GUIA-BASIC.md).

## Estado atual

Validado de ponta a ponta: o LIMO aparece no Gazebo, o RViz mostra o modelo e o
laser, o robô responde a `/cmd_vel`, a odometria acumula e a árvore TF está
conectada. O Gazebo roda com Real Time Factor 1.00 na GPU integrada.

```
.
├── Dockerfile
├── docker-compose.yml
├── GUIA-BASIC.md       # como usar (PT)
├── GUIA-BASIC.en.md    # como usar (EN)
├── README.md           # este arquivo: decisões e correções (PT)
├── README.en.md        # decisões e correções (EN)
├── patches/
│   └── limo_ros2-fixes.patch
└── ws/
    └── src/
        └── limo_ros2/  # clone do upstream, com 8 correções
```

---

# Parte 1 — Decisões de ambiente

## Por que Humble e Gazebo Classic

O repositório `agilexrobotics/limo_ros2` tem branch `humble` escrita para Gazebo
Classic: os plugins são `libgazebo_ros_ackermann_drive.so`,
`libgazebo_ros_ray_sensor.so`, `libgazebo_ros_camera.so`. Portar para
`gz`/Harmonic significaria reescrever todos os plugins, os xacro e os launch.
Humble é o par natural dessa base de código, e Gazebo Classic vem junto.

O aviso de fim de vida do Gazebo Classic (janeiro de 2025) aparece na barra da
janela e é esperado. Não afeta a simulação.

## Isolamento em relação ao outro container da máquina

A máquina já roda um container `ros2-docker` (ROS 2 Jazzy + MRS UAV System) com
`network_mode: host` e `ROS_DOMAIN_ID=0`.

Este ambiente usa `ROS_DOMAIN_ID=42`.

Como os dois containers compartilham a rede do host, o `ROS_DOMAIN_ID` é o
**único** mecanismo impedindo que os tópicos de um apareçam no outro. Mudar esse
valor sem verificar o que mais está rodando reintroduz o crosstalk. Para
conferir, com a simulação no ar: `ros2 topic list` não deve mostrar nada do
stack MRS UAV.

`network_mode: host` foi mantido porque simplifica o DDS (sem NAT, sem
configuração de discovery) — o custo é justamente depender do domínio para
isolar.

## Container roda como usuário não-root (UID/GID 1000)

Esta foi a decisão mais consequente do ambiente, e foi tomada **depois** de
investigar como o X funciona nesta máquina.

**O que foi descoberto:** a sessão é COSMIC sobre Wayland, com Xwayland em
`DISPLAY=:1`. O comando `xhost` reporta:

```
access control enabled, only authorized clients can connect
SI:localuser:pedroyujiharada
```

Ou seja, **não existe cookie de autenticação** (`~/.Xauthority` nem existia). O
Xwayland autoriza pela credencial do socket Unix (`SO_PEERCRED`): quem tem o UID
do usuário entra, quem não tem, não entra.

**Consequência:** um container rodando como root é rejeitado, e a solução usual
é `xhost +local:docker` a cada login. Rodando o container com **UID 1000**, ele
cai naquela regra automaticamente e o `xhost` se torna desnecessário — de forma
permanente, sem autostart nem script de sessão.

**Benefício adicional, igualmente importante:** com container root, tudo que o
`colcon build` gera no bind mount (`build/`, `install/`, `log/`) nasce
pertencendo ao root no host, e limpar ou editar exige `sudo`. Com UID 1000 os
arquivos nascem do usuário.

O container tem `sudo` sem senha, necessário porque o `rosdep install` instala
pacotes apt.

Detalhe de observação: `xhost +local:docker`, o comando usual, tem a palavra
`docker` puramente decorativa — o `xhost` só lê o prefixo `local:` e libera
qualquer usuário local. O equivalente preciso seria `xhost +SI:localuser:root`.
Nenhum dos dois é necessário aqui.

## `group_add: ["44", "992"]`

São os GIDs de `video` e `render` **no host** (`getent group video render`).
Como o container não roda mais como root, ele precisa pertencer a esses grupos
para abrir `/dev/dri/card*` e `/dev/dri/renderD*` — sem isso, adeus aceleração
por Mesa.

Esses números são específicos desta máquina. Em outro host, confira antes.

## `.Xauthority` montado, mas vazio

O volume foi mantido conforme a especificação original, e o arquivo existe no
host vazio (0 bytes). Duas razões:

1. Um bind mount cujo source não existe faz o Docker **criar um diretório** no
   lugar — `~/.Xauthority` viraria uma pasta.
2. Tentou-se gerar um cookie real com `xauth generate :1 . trusted`, que falhou:
   o Xwayland do COSMIC não expõe a extensão `SECURITY`. Não é contornável.

Fabricar um cookie com `mcookie` funcionaria, mas por um motivo torto — o
servidor não o conheceria, e a conexão passaria apenas pela regra de credencial
do socket. Seria um arquivo que aparenta autenticar sem autenticar. O arquivo
vazio é mais honesto e tem o mesmo efeito.

## Decisões do Dockerfile

| Decisão | Por quê |
|---|---|
| `ARG DEBIAN_FRONTEND` em vez de `ENV` | com `ENV` a variável ficaria gravada na imagem e todo `apt install` feito depois, dentro do container, herdaria o modo não-interativo silenciosamente |
| `rm -rf /var/lib/apt/lists/*` na mesma camada do `apt-get install` | é o que evita o cache do apt ficar gravado na imagem; em camada separada, o cache já teria sido commitado |
| Efeito colateral do item acima | o `rosdep install` dentro do container precisa de `sudo apt-get update` antes, senão não há índice de pacotes |
| `sudo` instalado em camada separada | o `apt-get install` principal é a camada cara; mantê-la intocada byte a byte faz o rebuild reaproveitar o cache |
| `rosdep init` ausente | a imagem `osrf/ros` já traz `/etc/ros/rosdep/sources.list.d/20-default.list`; chamar de novo falharia com "already exists" |
| `rosdep update` roda como o usuário `limo` | para o cache cair no `HOME` dele, que é quem vai executar o `rosdep install` |
| `--no-install-recommends` | imagem menor; pacotes `ros-*` declaram o que precisam em `Depends`. Se faltar algo gráfico, basta remover o flag |
| source condicional no `.bashrc` | `[ -f ~/ws/install/setup.bash ]` evita quebrar o shell antes do primeiro `colcon build` |

## `colcon build --symlink-install`

O `install/` aponta para os arquivos em `src/` em vez de copiá-los. Como `ws/` é
um bind mount, editar launch, `.xacro`, `.rviz` ou mundo **no host** passa a
valer dentro do container sem rebuildar. Durante a depuração descrita abaixo,
isso encurtou cada ciclo de teste de minutos para segundos.

---

# Parte 2 — Correções no limo_ros2

O upstream (`agilexrobotics/limo_ros2`, branch `humble`) **não builda e não roda**
sem os ajustes abaixo. Todos no pacote `limo_car`. Ver os diffs:
`cd ws/src/limo_ros2 && git diff`.

As três primeiras impedem o build. As quatro últimas só se manifestam em
execução: o pacote compila limpo e a simulação sobe quebrada.

## 1. `CMakeLists.txt` — install de diretórios inexistentes

```
install(DIRECTORY launch  gazebo log meshes rviz src urdf worlds ...)
```

`log`, `src` e `worlds` não existem no pacote, e o CMake aborta ao instalar um
diretório declarado e ausente. Removidos `log` e `src`. O `worlds` foi mantido
porque o diretório passou a existir (item 4).

## 2. `package.xml` — `<depend>rviz</depend>`

`rviz` é o nome do pacote no ROS 1. No ROS 2 é `rviz2`, e o `rosdep` não resolve
a chave `rviz`. Corrigido para `rviz2`.

Curiosidade que confirma o diagnóstico: o pacote `limo_description`, do mesmo
repositório, já tem essa linha **comentada** e o `rviz2` ativo. O autor corrigiu
lá e esqueceu aqui.

## 3. `package.xml` — `<depend>libgazebo_ros</depend>`

Não existe como pacote ROS nem como chave rosdep. Verificado por parse do
`distribution.yaml` oficial do Humble (2345 pacotes):

| chave | existe no Humble |
|---|---|
| `rviz` | não |
| `rviz2` | sim |
| `libgazebo_ros` | **não** |
| `gazebo_ros` | sim |

Corrigido para `gazebo_ros`. Sem isso, o `rosdep install` para com
`Cannot locate rosdep definition for [libgazebo_ros]`.

## 4. `worlds/empty_world.model` — mundo ausente

O launch monta `world_path` a partir de `worlds/empty_world.model`, arquivo que
não está no repositório.

**Havia duas saídas:** criar o mundo no pacote, ou apontar o launch para um mundo
já fornecido pelo `gazebo_ros`. **Escolhida a primeira**, por dois motivos:

1. O mundo fica versionado no workspace e **editável**. Ele é um bind mount do
   host, então adicionar obstáculos para exercitar SLAM e Nav2 é editar um
   arquivo. Um mundo do `gazebo_ros` viveria em `/opt/ros/humble/share/`, dentro
   da imagem, e qualquer edição morreria no próximo `docker compose build`.
2. Divergência mínima do upstream: repõe um arquivo que o autor claramente tinha
   e não commitou, em vez de reescrever o launch.

O mundo hoje tem ground plane, sol, uma sala fechada de 10x10 m, dois blocos e um
cilindro. Os obstáculos internos são **assimétricos de propósito**: paredes lisas
e simétricas dão poucas features ao scan matcher, e o mapa do `slam_toolbox`
escorrega.

## 5. `launch/ackermann_gazebo.launch.py` — o mundo nunca era carregado

Achado durante a leitura do launch: o `world_path` era passado como launch
argument para `ackermann.launch.py`, que **só declara `use_sim_time`** e ignora
o `world` por completo. O include que realmente sobe o Gazebo não recebia
argumento nenhum — o Gazebo abria sempre com o `empty.world` padrão do
`gazebo_ros`.

O `world_path` era, portanto, código morto. E como `os.path.join` apenas
concatena strings, sem tocar o disco, a pasta ausente **nunca causou erro no
launch** — quem quebrava era o `install()` do item 1.

Corrigido movendo `launch_arguments={'world': world_path}` para o include do
`gazebo_ros/gazebo.launch.py`. Sem isso, o mundo criado no item 4 seria editado
sem nenhum efeito visível — uma armadilha pior que o bug original.

## 6. `gazebo/ackermann_with_sensor.xacro` — a macro do robô nunca era chamada

**Sintoma:** `spawn_entity` preso em `Waiting for entity xml on
robot_description`, RViz sem dado nenhum, Gazebo vazio.

**Causa raiz:** o arquivo inclui `ackermann.xacro`, que **define** a macro
`limo_ackermann` — mas nunca a instancia. O URDF gerado saía com os três
sensores e seus joints apontando para um `base_link` que não existia. O
`robot_state_publisher` abortava (exit code -6):

```
Failed to build tree: parent link [base_link] of joint [depth_camera_joint] not found.
```

Sem ele, ninguém publicava `/robot_description` (confirmado:
`Publisher count: 0`), e o `spawn_entity` esperava para sempre.

**Correção:** adicionado `<xacro:limo_ackermann />`. O URDF saltou de 210 linhas
contendo apenas a sensórica para os 12 links do robô completo, com `base_link`
entre eles.

Detalhe que confunde o diagnóstico: `xacro` processa o arquivo **sem erro**, e
gera XML válido. O problema é semântico, não sintático — só o parser de URDF
reclama.

## 7. `gazebo/ackermann.xacro` — `base_footprint` comentado

**Sintoma:** com o robô já spawnando, o RViz mostrava `Global Status: Ok` e mesmo
assim não desenhava nada.

**Causa raiz:** o link `base_footprint` e o joint `base_joint` estavam dentro de
um comentário XML. Mas dois consumidores dependem desse frame: o plugin
(`<robot_base_frame>base_footprint</robot_base_frame>`) e o `gazebo.rviz` (Fixed
Frame). O resultado eram duas árvores TF desconexas:

| publicador | árvore |
|---|---|
| `ackermann_controller` (plugin Gazebo) | `odom → base_footprint → rodas` |
| `robot_state_publisher` (URDF) | `base_link → laser_link, depth_camera_link, imu_link` |

Veredito do `tf2_echo`: *"Could not find a connection between 'base_footprint'
and 'base_link' because they are not part of the same tree. Tf has two or more
unconnected trees."*

O RViz tinha o `/scan` em `base_link` e o Fixed Frame em `base_footprint`, sem
caminho entre os dois.

**Correção:** bloco descomentado, restaurando `base_footprint → base_link`
(offset de 0,15 m).

**Por que isto não cria publicador duplicado das rodas:** não há
`joint_state_publisher` no launch, então o `robot_state_publisher` não publica os
joints `continuous` (as rodas) — apenas os fixos. Quem publica as rodas é o
plugin. As duas fontes se complementam em vez de competir.

## Ajustes de usabilidade

Três itens menores, aplicados depois da simulação validada:

| Arquivo | Mudança | Por quê |
|---|---|---|
| `gazebo/sensor.xacro` | `<frame_name>${frame_prefix}_link</frame_name>` no plugin do laser | sem isso o Gazebo colapsa o `laser_link` (joint fixo) dentro do `base_link`, e o `/scan` saía com `frame_id: base_link` — o laser era medido do centro do chassi, ~12 cm atrás da posição física |
| `rviz/gazebo.rviz` | display `RobotModel` lendo `/robot_description` | a config do upstream tem Grid, LaserScan e Image, e nenhum deles desenha o robô |
| `worlds/empty_world.model` | sala e obstáculos | num mundo vazio todos os raios do lidar voltam no infinito e o RViz não tem o que mostrar |

## 8. `.gitignore` — a regra que provavelmente causou o bug 4

Ao versionar as correções, o mundo criado no item 4 não aparecia no
`git status`. Motivo:

```
.gitignore:117:*.mod*    limo_car/worlds/empty_world.model
```

O `.gitignore` do upstream tem `*.mod*`, que casa com `empty_world.model`.

Isso é quase certamente a **origem do bug 4**: o autor tinha o mundo na máquina
dele, o `.gitignore` o excluiu silenciosamente do commit, e o repositório foi
publicado com um launch apontando para um arquivo que só existia localmente.

Corrigido com uma exceção explícita:

```
!limo_car/worlds/*.model
```

Sem isso, o mesmo sumiço se repetiria no patch gerado a partir deste clone.

---

# Parte 3 — Versionamento

Duas camadas de git, de propósito:

**1. `~/limo-docker`** — repositório da infraestrutura: `Dockerfile`,
`docker-compose.yml`, a documentação e o patch. O `.gitignore` exclui os
artefatos de build (`ws/build/`, `ws/install/`, `ws/log/`) e o próprio clone do
`limo_ros2`, que tem git próprio.

**2. `ws/src/limo_ros2`** — clone do upstream. As correções estão commitadas na
branch local **`humble-fixes`**, sobre o commit `dcc5a86` do AgileX. Isso as
protege de um `git checkout` acidental.

**A ponte entre as duas:** `patches/limo_ros2-fixes.patch`, versionado no repo de
cima. Ele torna este repositório autossuficiente — não é preciso fork do
`limo_ros2`. Para reproduzir o ambiente do zero:

```bash
cd ws/src
git clone -b humble https://github.com/agilexrobotics/limo_ros2.git
cd limo_ros2
git am < ../../../patches/limo_ros2-fixes.patch
```

Se o upstream mudar e o `git am` recusar, `git apply --3way` costuma resolver.

Ao alterar o `limo_ros2` daqui em diante, commite na branch `humble-fixes` e
regenere o patch:

```bash
cd ws/src/limo_ros2
git format-patch dcc5a86 --stdout > ../../../patches/limo_ros2-fixes.patch
```

---

# Parte 4 — Método de diagnóstico

Vale registrar porque o mesmo caminho serve para o próximo problema.

Os itens 6 e 7 têm uma característica traiçoeira: **o pacote compila limpo**. O
`colcon build` termina com sucesso, a simulação abre, as janelas aparecem — e
nada funciona. Duas coisas destravaram o diagnóstico:

1. **Capturar o log do launch em arquivo**, em vez de rolar o terminal:
   `ros2 launch ... > /tmp/launch.log 2>&1`. O erro fatal do
   `robot_state_publisher` acontece nos primeiros 200 ms e fica soterrado por
   centenas de linhas de ruído do ALSA (o container não tem placa de som).

2. **Inspecionar o sistema vivo de outro terminal**, com
   `docker compose exec limo bash`:

   | Comando | O que revelou |
   |---|---|
   | `ros2 node list` | o `robot_state_publisher` não estava entre os nós |
   | `ros2 topic info /robot_description --verbose` | `Publisher count: 0` — descartou hipótese de QoS incompatível |
   | `ros2 run tf2_ros tf2_echo A B` | "two or more unconnected trees", em texto explícito |
   | `ros2 topic echo /tf --once` | mostrou o plugin publicando rodas a partir de `base_footprint` |

Uma hipótese foi testada e **descartada** pelo caminho: suspeitou-se de erro no
xacro, mas `xacro arquivo.xacro > /tmp/limo.urdf` rodou sem erro. Isso redirecionou
a investigação do gerador para o consumidor do URDF, que é onde estava o problema.

---

# Limitações conhecidas

- **Sem `joint_state_publisher`:** o `robot_state_publisher` não anima as rodas na
  visualização. Não afeta a física nem a navegação — o Gazebo é a fonte da
  verdade para o movimento.
- **`urdf/limo_ackerman_base.xacro` é órfão:** define um `base_footprint` correto,
  mas não é incluído por ninguém (só aparece numa linha comentada de
  `display_ackermann.launch.py`). Deixado intacto.
- **`limo_base/scripts/` não é instalado:** o `CMakeLists.txt` do pacote instala
  `launch` e `src`, mas não `scripts`. Não quebra o build e não faz parte da
  simulação em Gazebo.
- **Nav2 e slam_toolbox instalados, não configurados:** os pacotes estão na
  imagem, mas ainda não há launch de navegação nem arquivo de parâmetros.

# Próximos passos sugeridos

1. `slam_toolbox` em modo online assíncrono para mapear a sala.
2. Salvar o mapa e subir o Nav2 com AMCL.
3. Ajustar os parâmetros do Nav2 para cinemática ackermann — o padrão assume
   differential drive, e o LIMO não gira parado.
