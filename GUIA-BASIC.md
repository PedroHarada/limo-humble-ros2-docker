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

## 6. Inspecionar o que está acontecendo

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

## 7. Editar o cenário

O mundo fica em `ws/src/limo_ros2/limo_car/worlds/empty_world.model` e pode ser
editado no host, com qualquer editor. Contém uma sala fechada de 10x10 m, dois
blocos e um cilindro.

Para obstáculos pontuais, sem editar arquivo: aba **Insert** do Gazebo, escolha
uma forma e clique no chão. Some ao fechar o Gazebo.

Para que uma edição no arquivo valha, relance o launch — o mundo só é lido
quando o `gzserver` sobe.

## 8. Problemas comuns

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

## 9. Onde ficam as coisas

| No host | No container |
|---|---|
| `~/limo-docker/ws/` | `/home/limo/ws` |
| `~/limo-docker/ws/src/limo_ros2/` | `/home/limo/ws/src/limo_ros2` |

O workspace é um bind mount: o que você edita no host vale imediatamente no
container, e os arquivos gerados pelo build pertencem ao seu usuário.
