# Como ROS 2, Gazebo e Nav2 se comunicam neste ambiente

Este documento explica **como as peças deste robô simulado conversam entre si**:
o que é cada programa que sobe quando você roda a simulação, por quais canais
eles trocam informação, e por que o conjunto funciona.

Ele não pressupõe conhecimento de ROS 2. A seção 2 apresenta o vocabulário
mínimo — nó, tópico, serviço, ação, TF — e as seções seguintes usam esse
vocabulário para descrever o que este repositório realmente faz. Quem já
conhece ROS 2 pode pular direto para a seção 3.

Os outros dois documentos cobrem ângulos diferentes: o [README.md](README.md)
registra **o que foi feito e por quê** (as decisões de projeto e os bugs
corrigidos), e o [GUIA-BASIC.md](GUIA-BASIC.md) é o **manual de operação** (que
comando rodar para cada coisa).

Tudo aqui descreve a implementação real, já validada: os pacotes `limo_slam`,
`limo_nav2` e `limo_worlds` existem e funcionam.

---

## 1. O panorama, antes dos detalhes

A primeira coisa a entender é que **não existe "o programa do robô"**. O que
existe é um punhado de programas independentes, rodando ao mesmo tempo, cada um
resolvendo um pedaço do problema e trocando mensagens com os outros.

Quando você roda a simulação, sobem (pelo menos) estes:

| Programa | O que faz |
|---|---|
| `gzserver` | simula a física: o chão, as paredes, as rodas girando, o laser batendo nos objetos |
| `gzclient` | a janela 3D onde você vê a simulação (é só uma janela — desligá-la não para a física) |
| `robot_state_publisher` | sabe a forma do robô: onde fica o laser em relação ao chassi, onde ficam as rodas |
| `rviz2` | a tela de diagnóstico: desenha o que o robô "acha" que está vendo |
| `slam_toolbox` | constrói o mapa da sala enquanto o robô anda (só durante o mapeamento) |
| nós do Nav2 | decidem para onde ir e mandam o robô andar (só durante a navegação) |
| `obstacle_mover` | move os obstáculos móveis dentro da simulação (opcional) |

Nenhum deles chama função de outro. Eles **publicam e leem mensagens**, como
pessoas falando numa sala onde qualquer um pode ouvir quem quiser. Esse conjunto
de programas e das mensagens entre eles é o que se chama de **grafo ROS 2**.

Em traço grosso, o fluxo é este:

```
   o simulador finge ser o mundo real            a navegação finge ser um motorista
   ------------------------------------          -----------------------------------

   gzserver  --- "o laser está vendo isto" --->  Nav2  ---+
             --- "o robô está aqui"         --->          |
                                                          |
             <-------- "vá para frente, virando à esquerda"
```

O simulador entrega **o que os sensores enxergam**; a navegação devolve **o que
fazer com os motores**. A troca acontece por mensagens, e é justamente por isso
que o mesmo Nav2 rodaria igual num robô de verdade: ele nunca descobre que do
outro lado há um simulador em vez de motores e um laser físico.

## 2. O vocabulário do ROS 2

Cinco conceitos bastam para ler o resto do documento.

### 2.1 Nó: um programa participante

**Nó** é cada programa que participa do grafo. O `slam_toolbox` é um nó; o
`rviz2` é outro. Um nó pode rodar no seu computador, dentro de um container ou
em outra máquina da rede — para os demais, dá no mesmo.

Para ver quem está no ar: `ros2 node list`.

### 2.2 Tópico: o canal de transmissão contínua

**Tópico** é um canal com nome, onde um nó **publica** mensagens e qualquer
número de outros **assina** para recebê-las. É o canal do "toda hora, mais um
pedaço de informação": a leitura do laser, a posição do robô, a imagem da
câmera.

A analogia útil é a de uma estação de rádio. Quem transmite não sabe quem está
ouvindo, e não espera resposta. Quem ouve sintoniza o nome do canal (`/scan`,
`/odom`) e recebe tudo o que for transmitido dali em diante.

Três consequências dessa escolha, que aparecem o tempo todo neste ambiente:

- **Ninguém depende de ninguém.** O `gzserver` publica `/scan` haja quem
  escutar ou não. Você pode subir e matar o Nav2 no meio da simulação sem
  perturbar o simulador.
- **Vários podem ouvir o mesmo.** `/scan` é consumido ao mesmo tempo pelo RViz
  (para desenhar) e pelo Nav2 (para desviar de obstáculos).
- **Vários podem falar no mesmo canal.** `/cmd_vel` é o canal dos comandos de
  velocidade: tanto o teclado quanto o Nav2 publicam ali. O simulador obedece
  aos dois indistintamente — o que também significa que deixar os dois ligados
  ao mesmo tempo dá briga.

Para espiar um canal: `ros2 topic echo /scan`.

### 2.3 Serviço: o pedido com resposta

**Serviço** é uma chamada pontual: um nó pede, o outro responde. Não é um fluxo
contínuo, é uma pergunta com resposta — mais telefonema que rádio.

Serve para o que acontece uma vez, e onde interessa saber se deu certo:
"instancie este robô na simulação" (`/spawn_entity`), "coloque esta caixa nesta
posição" (`/gazebo/set_entity_state`).

Para listar: `ros2 service list`.

### 2.4 Ação: o pedido demorado, com acompanhamento

**Ação** é para tarefas que levam tempo e podem ser acompanhadas ou canceladas
no meio. "Vá até aquele canto da sala" é o exemplo perfeito: leva um minuto,
você quer saber o progresso, e quer poder desistir.

Uma ação tem três partes: o **objetivo** (para onde ir), o **feedback**
(a que distância está) e o **resultado** (chegou, falhou ou foi cancelado). Por
baixo, o ROS 2 constrói tudo isso com tópicos e serviços — mas quem usa lida
com a ação inteira.

No Nav2, a ação principal é `NavigateToPose`, e é o que o botão "Nav2 Goal" do
RViz aciona quando você clica um destino no mapa.

### 2.5 Mensagem e tipo

Toda troca carrega uma **mensagem** de um **tipo** definido. `sensor_msgs/LaserScan`
tem ângulo inicial, incremento angular e a lista de distâncias. `geometry_msgs/Twist`
tem velocidade linear e angular. Os tipos são o contrato: um nó que espera
`LaserScan` não aceita outra coisa no lugar.

Para descobrir o tipo de um canal: `ros2 topic info /scan`.

### 2.6 Parâmetro: a configuração de um nó

**Parâmetro** é um valor de configuração que o nó lê ao subir (e que pode ser
consultado depois). É como cada pacote deste repositório ajusta o comportamento
dos nós sem recompilar nada — os arquivos `.yaml` em `config/` são listas de
parâmetros.

O parâmetro mais importante aqui é o `use_sim_time`, explicado na seção 4.3.

### 2.7 TF: a árvore de "o que está onde"

Um robô é cheio de peças em posições diferentes, e cada sensor enxerga o mundo a
partir de onde ele está montado. O laser reporta "tem uma parede a 2 metros **na
minha frente**" — mas o laser está montado 10 cm à frente e 15 cm acima do
centro do robô, que por sua vez está em algum lugar da sala.

**TF** (de *transform*) é o sistema que mantém essas relações e faz a conversão
entre elas. Cada peça de referência é um **frame**, e os frames formam uma
árvore, cada um pendurado no anterior:

```
map            (a sala)
 └── odom      (de onde o robô partiu)
      └── base_footprint   (o robô, projetado no chão)
           └── base_link   (o corpo do robô)
                ├── laser_link        (o lidar)
                ├── depth_camera_link (a câmera)
                └── imu_link          (a IMU)
```

Com essa árvore montada, qualquer nó consegue responder "essa parede que o laser
viu, onde ela fica **na sala**?" — basta percorrer a corrente de transformadas.

O detalhe que morde: se **um elo faltar**, a árvore quebra em duas partes
desconexas e a pergunta deixa de ter resposta. Não aparece erro nos tópicos,
todos continuam publicando normalmente; simplesmente nada funciona. Foi
exatamente o que aconteceu neste repositório (README.md, correção nº 7).

Para conferir um elo: `ros2 run tf2_ros tf2_echo map odom`.

### 2.8 Launch file: a receita que sobe tudo

Subir dez nós na mão, cada um com seus parâmetros, seria inviável. Um **launch
file** (em ROS 2, um script Python) declara o que subir, com que configuração, e
pode incluir outros launch files. É o que você executa com `ros2 launch`.

### 2.9 Resumo dos três canais

| Canal | Quando usar | Espera resposta? | Exemplo aqui |
|---|---|---|---|
| **Tópico** | fluxo contínuo de dados | não | `/scan`, `/odom`, `/cmd_vel` |
| **Serviço** | operação pontual | sim, imediata | `/gazebo/set_entity_state` |
| **Ação** | tarefa demorada, cancelável | sim, com progresso | `NavigateToPose` |

## 3. A camada de transporte: DDS, não um `roscore`

Sabendo o que são nós e tópicos, falta uma pergunta: **como um nó encontra o
outro?**

No ROS 1 havia um processo central, o `roscore`, onde todos se registravam. O
ROS 2 não tem isso. Cada nó fala diretamente com os outros por **DDS** (Data
Distribution Service), o middleware de publish/subscribe que roda por baixo dos
panos (aqui, a implementação padrão do Humble, `rmw_fastrtps_cpp`). Os nós se
anunciam na rede por multicast UDP e se descobrem sozinhos — não existe
intermediário, e não há "servidor" para cair.

O preço dessa liberdade é que **qualquer nó na mesma rede pode ouvir qualquer
outro**, o que explica duas configurações deste ambiente:

- **`network_mode: host` no `docker-compose.yml`**: o container não tem rede
  isolada, usa a pilha do host diretamente. Sem isso, seria preciso configurar
  NAT e portas para a descoberta multicast atravessar a fronteira do container.
- **`ROS_DOMAIN_ID: 42`**: um número que separa grafos independentes na mesma
  rede — nós só se descobrem dentro do mesmo domínio. Como esta máquina roda
  outro container ROS 2 (ver README.md), e ambos compartilham a rede do host,
  esse número é a **única** coisa impedindo que um ouça o outro.

Todo o resto deste documento — tópicos, TF, `/clock` — viaja sobre esse
transporte.

## 4. O Gazebo dentro do grafo ROS 2

Agora a peça central: como um simulador de física vira participante de uma
conversa ROS 2.

O Gazebo Classic (`gzserver` + `gzclient`) **não é um nó ROS 2**. É um simulador
independente, que existiria mesmo sem ROS. A ponte é o pacote `gazebo_ros`, que
carrega **plugins** dentro do processo do `gzserver`.

Um plugin é uma biblioteca (`.so`) que o Gazebo carrega na inicialização e passa
a executar como parte de si mesmo. Esses plugins específicos usam a API do ROS 2
(`rclcpp`) para publicar e assinar tópicos. O resultado é que, visto de fora, o
`gzserver` **se comporta como se fosse vários nós ROS 2** — e nenhum outro
programa tem como saber a diferença.

### 4.1 O launch que sobe tudo

`ros2 launch limo_car ackermann_gazebo.launch.py` executa, em sequência:

1. **`ackermann.launch.py`** → sobe o `robot_state_publisher`. Esse nó lê a
   descrição do robô (um arquivo XACRO, `ackermann_with_sensor.xacro`, que ele
   converte em URDF — o formato que descreve peças, juntas e sensores), publica
   essa descrição em `/robot_description` e passa a manter a parte **fixa** da
   árvore TF: onde cada sensor está montado em relação ao corpo.
2. **`gazebo_ros/launch/gazebo.launch.py`** → sobe o `gzserver` (a física) e o
   `gzclient` (a janela 3D), carregando o arquivo do mundo — por padrão
   `worlds/empty_world.model`, a sala de 10x10 m.
3. **`spawn_entity.py`** → um nó que lê `/robot_description` e **pede ao
   `gzserver`, por um serviço**, que crie aquele robô dentro da simulação. É o
   elo entre "descrição publicada no grafo ROS 2" e "objeto físico existindo no
   simulador".
4. **`rviz2`** → assina os tópicos publicados pelos plugins e desenha o robô, o
   laser e a imagem da câmera.

### 4.2 Os plugins e o que cada um publica

Os plugins são declarados dentro do XACRO/URDF, em blocos `<gazebo>`, e passam a
valer quando o robô é criado na simulação:

| Plugin (`.so`) | Papel | Tópicos ROS 2 |
|---|---|---|
| `libgazebo_ros_ackermann_drive.so` | controlador de tração e direção Ackermann | assina `/cmd_vel` (`geometry_msgs/Twist`); publica `/odom` (`nav_msgs/Odometry`) e o TF `odom → base_footprint` |
| `libgazebo_ros_ray_sensor.so` | lidar 2D | publica `/scan` (`sensor_msgs/LaserScan`) |
| `libgazebo_ros_camera.so` | câmera de profundidade | publica `/depth_camera/rgb/image_raw`, `/depth_camera/depth/image_raw`, `camera_info`, `points` (nuvem de pontos) |
| `libgazebo_ros_imu_sensor.so` | IMU | publica `/limo/imu` (`sensor_msgs/Imu`) |

O primeiro é o mais ilustrativo. Ele assina `/cmd_vel`, e quem publica ali pode
ser o `rqt_robot_steering` (você arrastando um slider), o
`teleop_twist_keyboard` (você apertando teclas) ou o Nav2 (um algoritmo
decidindo). O plugin não sabe e não precisa saber qual dos três é: recebe um
`Twist`, gira as rodas simuladas de acordo.

### 4.3 O relógio: `use_sim_time` e `/clock`

Numa simulação, o tempo não é o do relógio de parede. Se a física roda mais
devagar que o tempo real (ou mais rápido), um nó que consulte o relógio do
sistema vai discordar do simulador sobre **quando** cada leitura aconteceu.

Para resolver isso, o `gzserver` publica `/clock` (`rosgraph_msgs/Clock`) com o
tempo simulado, e todo nó que precisa concordar com ele recebe o parâmetro
`use_sim_time: true` — `robot_state_publisher`, `slam_toolbox`, os nós do Nav2 e
o `obstacle_mover`.

Quando um nó fica de fora dessa combinação, o sintoma é característico: as
mensagens chegam com timestamp "do futuro" ou "do passado" em relação aos
outros, e são descartadas por tolerância de tempo. Tudo parece publicar
normalmente e nada funciona — é o item mais citado na tabela de problemas do
`GUIA-BASIC.md`.

### 4.4 TF: as duas árvores que precisam se encontrar

Neste ambiente, a árvore TF é alimentada por **duas fontes independentes**:

- o `robot_state_publisher` publica a parte fixa, a partir de `base_link`: onde
  está cada sensor no corpo do robô;
- o `libgazebo_ros_ackermann_drive.so` publica a parte que muda, a partir de
  `base_footprint`: onde o robô está no mundo, segundo a odometria.

O elo `base_footprint → base_link` é o que junta as duas em uma árvore só. Sem
ele — que foi exatamente o bug documentado no README — RViz, SLAM e Nav2 recebem
duas árvores desconexas, e nenhum consegue responder onde uma leitura de laser
cai no mundo.

## 5. SLAM: construir o mapa enquanto anda

**SLAM** (*Simultaneous Localization and Mapping*) é o problema de descobrir ao
mesmo tempo como é o ambiente e onde o robô está dentro dele. O pacote
`limo_slam` (deste repositório, não do upstream) configura o `slam_toolbox` para
essa tarefa.

O ponto didático: o `slam_toolbox` é **um nó ROS 2 comum**. Ele não tem
nenhuma ligação especial com o Gazebo — só assina tópicos que por acaso um
simulador está publicando.

```
gzserver (plugins) --/scan--------> slam_toolbox --/map------> RViz
                   --/tf (odom→base_footprint)--^
                   --/clock (use_sim_time)-------^
```

O `slam_toolbox` (`async_slam_toolbox_node`) assina `/scan` e `/tf`, e publica:

- **`/map`** (`nav_msgs/OccupancyGrid`), a grade de ocupação: a sala dividida em
  células, cada uma marcada como livre, ocupada ou desconhecida. É a imagem que
  aparece no RViz durante o mapeamento.
- **o elo de TF `map → odom`**, que fecha a árvore completa
  `map → odom → base_footprint → base_link → sensores`.

Esse segundo item merece atenção, porque é sutil. A odometria (contar quanto as
rodas giraram) acumula erro: depois de alguns minutos, o robô "acha" que está
num lugar e está em outro. O elo `map → odom` é a **correção** desse desvio,
calculada por quem consegue reconhecer o ambiente.

Quem publica essa correção muda conforme a tarefa: durante o mapeamento é o
`slam_toolbox`; durante a navegação, contra um mapa já salvo, é o `amcl` do
Nav2. Nunca os dois ao mesmo tempo — seriam duas respostas concorrentes para a
mesma pergunta.

## 6. Nav2: decidir para onde ir (pacote `limo_nav2`)

O Nav2 é um **conjunto de nós ROS 2 comuns**, e vale insistir nisto: ele não
tem relação nenhuma com o Gazebo. Não sabe se `/scan` e `/odom` vêm de um
simulador ou de um robô físico. Só assina e publica tópicos, como o
`slam_toolbox`. É por isso que ele "simplesmente funciona" sobre uma simulação —
está a duas camadas de distância dela, conversando apenas com o grafo ROS 2.

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

Cada peça, e o que ela faz no grafo (as decisões de configuração estão no
README.md, Parte 4):

- **`map_server`** — carrega o mapa salvo (`.yaml` + `.pgm`, gerados conforme a
  seção 6 do `GUIA-BASIC.md`) e o publica em `/map`. Mesma informação que o
  `slam_toolbox` publicava, mas vinda de um arquivo em vez de scans ao vivo.
- **`amcl`** — a localização. Assina `/scan`, `/map` e `/tf`, compara o que o
  laser vê agora com o mapa guardado, e conclui onde o robô está. O nome vem de
  *Adaptive Monte Carlo Localization*: ele mantém centenas de palpites
  ("partículas") espalhados pelo mapa e vai eliminando os que não batem com as
  leituras. O resultado é publicado como o elo de TF `map → odom`.
- **`nav2_costmap_2d`** — o mapa de custos, em duas instâncias. O **global**
  cobre a sala inteira e serve para traçar a rota; o **local** cobre alguns
  metros ao redor do robô e é redesenhado continuamente a partir do `/scan`.
  "Custo" aqui é quão indesejável é passar por cada célula: obstáculos são
  intransponíveis, e as células ao redor deles recebem custo alto (o robô tem
  largura, e raspar na parede não serve).
- **`planner_server`** — traça o caminho do ponto atual até o destino, sobre o
  costmap global. Pensa na rota inteira, sem se preocupar com como executá-la.
- **`controller_server`** — pega esse caminho e o transforma em comandos de
  velocidade, olhando o costmap local para desviar do que aparecer pelo
  caminho. É ele quem publica em **`/cmd_vel`** — o mesmo tópico em que você
  publica ao arrastar o slider do `rqt_robot_steering`.
- **`bt_navigator`** — o maestro. Coordena os anteriores por uma *Behavior Tree*
  (uma árvore de decisões: tente planejar; se falhar, espere; se ainda falhar,
  recue) e expõe tudo isso como a ação `NavigateToPose`, que é o que o botão
  "Nav2 Goal" do RViz aciona.

### 6.1 A complicação deste robô: cinemática Ackermann

O Nav2 assume, por padrão, um robô de **tração diferencial** — duas rodas
independentes, que giram em sentidos opostos para o robô rodar no próprio eixo.
O LIMO simulado aqui é **Ackermann**: tem direção, como um carro. E um carro
**não gira parado**: com velocidade linear zero, esterçar as rodas não move
nada (o `GUIA-BASIC.md` documenta isso em "Particularidade do ackermann").

Isso não é um problema de comunicação — os tópicos e as mensagens são os mesmos.
É um problema de **quem decide os comandos**: o controlador padrão do Nav2
(`DWB`) pediria rotações no lugar, o robô não obedeceria, e a navegação falharia
por esgotar a paciência do controlador.

A solução foi trocar o controlador por `RegulatedPurePursuitController`, que
segue o caminho mirando um ponto à frente e respeita um raio de curvatura
mínimo, calculado a partir da distância entre eixos (`wheelbase`) e do esterço
máximo (`max_steer`) reais do robô. Detalhes no README.md, Parte 4.

## 7. Obstáculos móveis: a seta que aponta para dentro do simulador

Até aqui, tudo **lê** o Gazebo: os plugins publicam `/scan`, `/odom`, `/clock`,
e os nós ROS 2 consomem. O `obstacle_mover` (pacote `limo_worlds`) é o único
componente que faz o caminho inverso: ele **escreve** no simulador, mudando o
mundo enquanto a simulação roda.

Para que serve: o Nav2 navegando contra um mapa salvo só encontra o que já
estava no mapa. Para ver replanejamento de verdade, é preciso um obstáculo que o
mapa desconhece e que se mova durante a navegação.

O canal aqui é um **serviço**, não um tópico:

```
obstacle_mover --/gazebo/set_entity_state (srv, 30 Hz)--> gzserver
                                                             |
                                        muda a pose do modelo crossing_box
                                                             |
                                                  o raycast do lidar bate nela
                                                             |
gzserver --/scan--> nav2_costmap_2d (local) --> controller_server --/cmd_vel-->
```

Quem oferece esse serviço é mais um plugin dentro do `gzserver`,
`libgazebo_ros_state.so`, declarado no `dynamic_world.model`. Vale a observação
da seção 4: ele roda como parte do Gazebo, mas fala ROS 2, então para o grafo é
um provedor de serviço como outro qualquer.

**Por que serviço e não tópico:** cada chamada é um pedido pontual com
confirmação — "coloque esta caixa nesta pose", e o Gazebo responde se conseguiu.
Como isso é uma ida e volta, o `obstacle_mover` dispara as chamadas de forma
assíncrona e não espera a resposta, senão o relógio de 30 Hz dele travaria a
cada envio.

### 7.1 Por que o obstáculo é `<model>` e não `<actor>`

O SDF (o formato dos mundos do Gazebo) tem um recurso feito sob medida para
isto: o `<actor>`, que anima um objeto por uma lista de posições, sem exigir
nenhum programa externo. Ele tornaria todo o `obstacle_mover` desnecessário.

Ele não funciona aqui, e falha do pior jeito possível: o Gazebo Classic **não
entrega as colisões de um ator aos sensores de raio**. A caixa se moveria na
tela, e o laser atravessaria ela como se não existisse — nada no `/scan`, nada
no costmap, Nav2 completamente alheio. Os números medidos estão no README.md,
Parte 5: apontado para um ator a 2,5 m, o laser reportou a parede atrás dele.

Por isso cada obstáculo móvel é um `<model>` comum, com colisão de verdade, e
marcado como `kinematic` — a física não o move nem o deixa cair, mas ele existe
para o raycast do laser. O custo dessa escolha é que alguém de fora precisa
atualizar a pose dele, e esse alguém é o `obstacle_mover`.

### 7.2 O que o Nav2 vê

Nada de novo — e é esse justamente o ponto.

O obstáculo não entra no `/map` do `map_server`, porque aquele mapa foi salvo
antes, com a sala vazia. Ele aparece no `/scan`, que alimenta o **costmap
local**. A navegação percebe a diferença entre "o que o mapa diz que existe" e
"o que o laser está vendo agora", e é essa diferença que faz o
`controller_server` desviar. É exatamente o mecanismo que o `limo_worlds` existe
para exercitar.

## 8. Resumo do fluxo de mensagens

```
              use_sim_time=true, /clock
                       |
   +-------------------+-------------------+
   |                                       |
   v                                       v
gzserver (plugins Gazebo)  <----/cmd_vel---+---- rqt_robot_steering /
   |   |   |         ^                           teleop_twist_keyboard
   |   |   |         +--/gazebo/set_entity_state (srv)-- obstacle_mover
   |   |   +--/limo/imu------------------> (não consumido hoje)
   |   +--/depth_camera/*----------------> RViz
   +--/scan---------------+---------------> RViz
   |                      |
   +--/odom, /tf----------+
                           v
                    slam_toolbox --/map, tf(map→odom)--> RViz (slam.rviz)
```

Três leituras deste desenho:

- **O Nav2 ocupa o mesmo lugar do `slam_toolbox`**: consome `/scan`, `/odom` e
  `/tf`, e devolve `/cmd_vel` no lugar do teleop. Nada precisa mudar no Gazebo,
  nos plugins ou na TF para trocar um pelo outro.
- **SLAM e Nav2 não rodam juntos**: o `slam_toolbox` serve para **gerar** o
  mapa; o Nav2 depois **localiza** contra o mapa salvo. Os dois publicariam o
  mesmo elo `map → odom`.
- **O `obstacle_mover` é ortogonal aos dois**: mexe no mundo, não no robô. Roda
  junto com o Nav2 (é o caso de uso) e até com o SLAM — mas aí o obstáculo
  entraria no mapa como um rastro, que é justamente o que não se quer num mapa
  estático.

## 9. Ver acontecendo, em vez de acreditar

Com a simulação no ar, estes comandos mostram cada afirmação deste documento:

| O que conferir | Comando |
|---|---|
| quem está no grafo | `ros2 node list` |
| quais canais existem | `ros2 topic list` |
| o que passa num canal | `ros2 topic echo /scan` |
| a que taxa | `ros2 topic hz /scan` |
| o tipo e quem fala/ouve | `ros2 topic info /cmd_vel --verbose` |
| um elo da árvore TF | `ros2 run tf2_ros tf2_echo map odom` |
| a árvore TF inteira, em PDF | `ros2 run tf2_tools view_frames` |
| serviços disponíveis | `ros2 service list` |
| se um nó usa tempo simulado | `ros2 param get /slam_toolbox use_sim_time` |
| o grafo desenhado | `rqt_graph` |

Um experimento que ensina mais que qualquer parágrafo acima: com a simulação
rodando, execute `ros2 topic echo /cmd_vel` numa janela e dirija o robô pelo
teclado em outra. As mensagens que você vê passando são exatamente as mesmas
que o Nav2 publicaria — é literalmente o mesmo canal, o mesmo tipo de mensagem,
o mesmo destinatário.

## 10. Glossário

| Termo | O que é |
|---|---|
| **nó** | um programa participante do grafo ROS 2 |
| **grafo** | o conjunto de nós e das conexões entre eles |
| **tópico** | canal nomeado de mensagens contínuas, sem resposta |
| **serviço** | pedido pontual com resposta imediata |
| **ação** | pedido demorado, com progresso e cancelamento |
| **mensagem / tipo** | o dado trafegado e o contrato que define seu formato |
| **parâmetro** | valor de configuração lido por um nó |
| **DDS** | o middleware que transporta tudo isso pela rede |
| **`ROS_DOMAIN_ID`** | número que separa grafos independentes na mesma rede |
| **TF / frame** | sistema de coordenadas relativas e cada referencial dele |
| **URDF / XACRO** | a descrição do robô (peças, juntas, sensores); XACRO é URDF com macros |
| **SDF** | o formato dos mundos do Gazebo |
| **plugin do Gazebo** | biblioteca carregada dentro do simulador; aqui, as que falam ROS 2 |
| **odometria** | estimativa de deslocamento pela rotação das rodas; acumula erro |
| **grade de ocupação** | o mapa como células livres, ocupadas ou desconhecidas |
| **costmap** | a grade com custo de passagem, usada para planejar e desviar |
| **SLAM** | mapear e se localizar ao mesmo tempo |
| **AMCL** | localização por partículas contra um mapa já pronto |
| **Behavior Tree** | árvore de decisões que orquestra o comportamento do Nav2 |
| **Ackermann** | direção tipo carro; não gira no próprio eixo |

---

*Este documento descreve o comportamento observado e validado em todo o
ambiente: Gazebo, SLAM (`limo_slam`), Nav2 (`limo_nav2`, README.md Parte 4) e
obstáculos móveis (`limo_worlds`, Parte 5). A única combinação ainda não
exercitada é o Nav2 navegando com os obstáculos em movimento.*
