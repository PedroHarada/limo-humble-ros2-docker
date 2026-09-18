# Guia básico de uso

*[English version](GUIA-BASIC.en.md)*

Como subir o ambiente e operar as ferramentas dentro do container. Para o
registro das decisões de projeto e das correções aplicadas ao `limo_ros2`, veja
o [README.md](README.md).

---

## 1. Primeira vez

Uma única vez, no host:

```bash
cd ~/limo-docker
./setup.sh
docker compose build
```

O `setup.sh` faz três coisas, e é idempotente (pode rodar de novo sem medo):

1. Detecta o UID/GID do seu usuário e os GIDs dos grupos `video` e `render`
   desta máquina, gravando tudo em `.env`. Esses números variam entre
   distribuições, e são o que dá ao container acesso à GPU e o dono correto dos
   arquivos.
2. Garante que o arquivo de autoridade do X exista (e usa o `$XAUTHORITY`
   correto, que em GNOME/Wayland não é `~/.Xauthority`).
3. Clona o `limo_ros2` em `ws/src/` e aplica as correções de
   `patches/limo_ros2-fixes.patch`. **Sem esse passo não há o que compilar** — o
   repositório não versiona o código do robô, só o patch.

Rode o `setup.sh` a partir de um terminal da sua sessão gráfica, senão ele não
consegue descobrir o `DISPLAY`.

O `docker compose build` demora alguns minutos (a imagem base
`osrf/ros:humble-desktop-full` tem alguns GB). Depois, com o container no ar, o
workspace precisa ser compilado uma vez — veja a seção 3.

## 2. Rotina de todo dia

```bash
cd ~/limo-docker
docker compose up -d              # sobe o container em background
docker compose exec limo bash     # abre um shell dentro dele
```

Para abrir **mais terminais** no mesmo container, repita `docker compose exec
limo bash` em outra janela do host. Você vai querer pelo menos três: um para a
simulação, um para o controle e um para inspecionar tópicos.

Ao terminar:

```bash
docker compose down
```

Não é preciso rodar `xhost` — o container roda com o mesmo UID do seu usuário e
o Xwayland já o autoriza. O porquê está no README.

## 3. Compilar o workspace

Dentro do container:

```bash
cd ~/ws
sudo apt-get update                              # só na primeira vez após o build
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
source install/setup.bash
```

Depois do primeiro build, o `source` é automático em todo shell novo (está no
`.bashrc`).

**Quando é preciso rebuildar:** só ao mexer em código C++ ou adicionar pacotes.
Por causa do `--symlink-install`, editar launch files, `.xacro`, `.rviz` ou
mundos **no host** já vale dentro do container — basta relançar.

## 4. Rodar a simulação

```bash
ros2 launch limo_car ackermann_gazebo.launch.py
```

Sobe três coisas: o Gazebo com a sala de 10x10 m, o LIMO na origem, e o RViz já
configurado com o modelo do robô, o laser e a imagem da câmera.

Deixe esse terminal ocupado com a simulação. `Ctrl+C` encerra tudo.

## 5. Dirigir o robô

### Opção A: sliders (mais fácil)

Em outro terminal do container:

```bash
ros2 run rqt_robot_steering rqt_robot_steering
```

1. No campo de texto do topo, escreva `/cmd_vel` e tecle Enter.
2. Slider **vertical** = velocidade linear (m/s). **Horizontal** = angular (rad/s).
3. Comece com máximos modestos: `0.3` linear e `0.5` angular.
4. O botão **Stop** zera os dois. Use-o antes de fechar a janela, senão o último
   comando continua valendo e o robô segue andando.

### Opção B: teclado

```bash
ros2 run teleop_twist_keyboard teleop_twist_keyboard
```

As teclas são fixas no pacote (não há arquivo de configuração):

```
u    i    o        i = frente             k = parar
j    k    l        , = ré                 j / l = girar no lugar
m    ,    .        u, o, m, . = curvas
```

Velocidade: `q`/`z` altera as duas, `w`/`x` só a linear, `e`/`c` só a angular.

**O terminal precisa estar em foco.** Se você clicar na janela do Gazebo, o
robô para de responder às teclas.

### Particularidade do ackermann

Com a velocidade linear em **zero**, mexer no angular não faz nada. Um carro com
direção não gira parado: as rodas viram, mas ele não sai do lugar. Dê velocidade
linear primeiro, depois esterce.

## 6. Mapear a sala com SLAM

O pacote `limo_slam` traz o `slam_toolbox` já configurado para este robô. Ele é
do seu workspace, não do upstream do AgileX.

Compilar, uma vez só (é um pacote novo, o `--symlink-install` não dispensa o
build):

```bash
cd ~/ws
colcon build --symlink-install --packages-select limo_slam
source install/setup.bash
```

Com a **simulação já rodando** em outro terminal:

```bash
ros2 launch limo_slam slam.launch.py
```

Isso sobe o `slam_toolbox` e uma **segunda** janela do RViz, com Fixed Frame em
`map` e o display do mapa. A janela do RViz que veio junto com a simulação
continua em `base_footprint` e não mostra o mapa — pode minimizá-la.

Argumentos aceitos:

| Argumento | Padrão | Para que serve |
|---|---|---|
| `rviz:=false` | `true` | sobe só o SLAM, sem abrir o segundo RViz |
| `use_sim_time:=false` | `true` | só faria sentido com robô real |
| `params_file:=/caminho/x.yaml` | o do pacote | testar parâmetros sem editar o original |

Confira que está de pé:

```bash
ros2 topic hz /map                    # publica a cada ~5 s
ros2 run tf2_ros tf2_echo map odom    # o elo que o slam_toolbox acrescenta
```

Agora é dirigir (seção 5) e ver o mapa crescer no RViz.

### Como dirigir para sair um mapa bom

**O lidar enxerga 240°, não 360°.** No `sensor.xacro` o campo de visão vai de
-2.09 a +2.09 rad: o LIMO vê à frente e aos lados, e é cego atrás. Andar só para
a frente deixa buracos — dê a volta pela sala nos dois sentidos.

**Vá devagar.** O scan matcher casa scans consecutivos; velocidade alta com
lidar a 8 Hz produz saltos grandes entre leituras, e o mapa sai torto.

**Parado, nada acontece.** Com `minimum_travel_distance: 0.1`, um scan novo só é
processado a cada 10 cm percorridos. É de propósito: processar scans com o robô
parado só acumula ruído.

### Salvar o mapa

```bash
mkdir -p ~/ws/maps
ros2 run nav2_map_server map_saver_cli -f ~/ws/maps/sala
```

Gera `sala.pgm` (a imagem) e `sala.yaml` (resolução, origem e limiares). Como
`~/ws` é o bind mount, os dois aparecem no host em `~/limo-docker/ws/maps/`, com
o seu usuário. São a entrada do Nav2 depois.

### Se o mapa sair ruim

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| Mapa vazio, nada aparece | o SLAM não recebe `/scan` ou não há TF | `ros2 topic hz /scan` e `ros2 run tf2_ros tf2_echo map odom` |
| Paredes duplicadas ou "fantasmas" | odometria escorregando, scan matcher perdendo o casamento | dirija mais devagar; volte a um trecho já mapeado para forçar fechamento de loop |
| Mapa só cresce à frente do robô | o campo de visão de 240° | percorra a sala nos dois sentidos |
| Mapa não atualiza enquanto ando | `use_sim_time` incoerente entre os nós | todos precisam de `use_sim_time: true`; confira com `ros2 param get /slam_toolbox use_sim_time` |

## 7. Navegar com Nav2

O pacote `limo_nav2` traz o Nav2 configurado para este robô: AMCL para
localização contra um mapa salvo, costmaps 2D a partir do `/scan`, e o
controlador `RegulatedPurePursuitController` no lugar do `DWB` padrão — o
`DWB` assume tração diferencial e giraria o robô no lugar, o que o LIMO
(Ackermann) não faz.

**Pré-requisito:** um mapa salvo (seção 6). O launch usa `~/ws/maps/sala.yaml`
por padrão.

Compilar, uma vez só:

```bash
cd ~/ws
colcon build --symlink-install --packages-select limo_nav2
source install/setup.bash
```

Com a **simulação já rodando** em outro terminal (relance-a do zero se o robô
não estiver mais na origem — o mapa foi salvo com o robô partindo de (0,0,0),
e o Nav2 assume essa mesma pose inicial):

```bash
ros2 launch limo_nav2 nav2.launch.py
```

Isso sobe o `map_server`, o `amcl`, os costmaps local e global, o
`planner_server`, o `controller_server`, o `bt_navigator` (via
`nav2_bringup`) e um RViz com a ferramenta **Nav2 Goal**. Diferente do
`slam.launch.py`, o robô já nasce localizado — não é preciso o "2D Pose
Estimate" manual.

Argumentos aceitos:

| Argumento | Padrão | Para que serve |
|---|---|---|
| `map:=/caminho/outro.yaml` | `~/ws/maps/sala.yaml` | usar outro mapa salvo |
| `params_file:=/caminho/x.yaml` | o do pacote | testar parâmetros sem editar o original |
| `rviz:=false` | `true` | sobe só o Nav2, sem abrir o RViz |
| `use_sim_time:=false` | `true` | só faria sentido com robô real |

Para mandar o robô a um destino: clique **Nav2 Goal** na barra de ferramentas
do RViz, depois clique e arraste no mapa (arrastar define a orientação final).
Confira que está de pé:

```bash
ros2 topic list | grep navigate_to_pose    # a acao do bt_navigator
ros2 lifecycle get /amcl                   # deve responder "active"
```

### Se o robô não sai do lugar

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| `RegulatedPurePursuitController detected collision ahead!` em loop, sem mover | o mapa tem "paredes fantasmas" perto do robô (mapeamento apressado ou incompleto) | refaça o mapeamento (seção 6) dirigindo mais devagar e dando a volta completa na sala |
| Nunca sai do estado `active` esperado, ou os tópicos de `/amcl` não aparecem | a pose inicial fixa (0,0,0) não bate com a pose real do robô | relance a simulação do zero (`ros2 launch limo_car ackermann_gazebo.launch.py`) antes do Nav2, para o robô voltar à origem |
| Objetivo aceito mas cancela logo depois | objetivo fora da área mapeada, ou dentro de um obstáculo inflado | escolha um ponto mais central no mapa, longe das paredes |

## 8. Inspecionar o que está acontecendo

| Objetivo | Comando |
|---|---|
| Listar nós ativos | `ros2 node list` |
| Listar tópicos | `ros2 topic list` |
| Ver comandos enviados | `ros2 topic echo /cmd_vel` |
| Ver a odometria | `ros2 topic echo /odom --field pose.pose.position` |
| Ver o laser (cabeçalho) | `ros2 topic echo /scan --once --field header` |
| Frequência de um tópico | `ros2 topic hz /scan` |
| Conferir uma transformada | `ros2 run tf2_ros tf2_echo base_footprint laser_link` |
| Árvore TF completa em PDF | `ros2 run tf2_tools view_frames` |
| Grafo de nós e tópicos | `rqt_graph` |

Tópicos principais da simulação:

| Tópico | Conteúdo |
|---|---|
| `/cmd_vel` | comando de velocidade (entrada) |
| `/odom` | odometria do plugin ackermann |
| `/scan` | lidar 2D, 720 amostras, alcance 8 m |
| `/imu` | IMU |
| `/depth_camera/image_raw` | câmera de profundidade |
| `/tf`, `/tf_static` | árvore de transformadas |

## 9. Editar o cenário

O mundo fica em `ws/src/limo_ros2/limo_car/worlds/empty_world.model` e pode ser
editado no host, com qualquer editor. Contém uma sala fechada de 10x10 m, dois
blocos e um cilindro.

Para obstáculos pontuais, sem editar arquivo: aba **Insert** do Gazebo, escolha
uma forma e clique no chão. Some ao fechar o Gazebo.

Para que uma edição no arquivo valha, relance o launch — o mundo só é lido
quando o `gzserver` sobe.

## 10. Problemas comuns

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| `cannot open display` | `DISPLAY` não exportado no terminal do host antes do `up` | `echo $DISPLAY` no host; se vazio, feche e reabra o terminal e refaça `docker compose up -d` |
| Robô não responde ao teclado | terminal do teleop sem foco | clique no terminal do teleop |
| Robô não gira | velocidade linear em zero | dê linear antes do angular |
| Robô continua andando sozinho | último `cmd_vel` ficou valendo | `Stop` no rqt, ou `k` no teleop |
| RViz sem nada na tela 3D | Fixed Frame sem TF | `ros2 run tf2_ros tf2_echo base_footprint base_link` |
| Gazebo abre preto ou trava | renderização por GPU | teste `LIBGL_ALWAYS_SOFTWARE=1` no `environment:` do compose (bem mais lento) |
| `groups: cannot find name for group ID 992` | grupo `render` sem nome dentro do container | cosmético, ignore |
| Mensagens de erro do ALSA | container sem placa de som | cosmético, ignore |

## 11. Onde ficam as coisas

| No host | No container |
|---|---|
| `~/limo-docker/ws/` | `/home/limo/ws` |
| `~/limo-docker/ws/src/limo_ros2/` | `/home/limo/ws/src/limo_ros2` |

O workspace é um bind mount: o que você edita no host vale imediatamente no
container, e os arquivos gerados pelo build pertencem ao seu usuário.
