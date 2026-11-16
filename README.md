# Ath10kMac

[Português (Brasil)](#português-brasil) | [English](#english)

## Português (Brasil)

Ath10kMac é uma extensão de kernel (kext) para macOS, criada para as placas Wi-Fi **Qualcomm Atheros QCA6174 e QCA9377**. O driver foi desenvolvido em C++/IOKit, usando o **ath10k do Linux** como referência para os protocolos, a inicialização do hardware e a comunicação com o firmware.

**A QCA6174 foi confirmada funcional no notebook testado com a versão 0.0.92, incluindo o retorno do repouso. A versão 0.0.93 adiciona seleção automática de board; esta atualização e o funcionamento completo da QCA9377 ainda precisam de validação em hardware.**

### Compatibilidade

| Placa | Identificação PCI | Situação |
| --- | --- | --- |
| **QCA6174** | `168c:003e` | **Validada na 0.0.92 no notebook testado**, com conexão, tráfego em 2,4 GHz e 5 GHz e recuperação após o repouso. A seleção automática da 0.0.93 aguarda teste em hardware. |
| **QCA9377** | `168c:0042` | **Experimental.** A 0.0.93 corrige a ausência de seleção de board Lenovo `17aa:0901`; inicialização completa, conexão e repouso ainda precisam ser confirmados. |

O projeto tem como alvo o **macOS em computadores Intel (x86_64)**. Os testes atuais foram realizados no **macOS Sequoia**. A confirmação de funcionamento da QCA6174 se refere ao notebook e às redes utilizados nos testes; outras revisões de placa e configurações ainda precisam de relatos da comunidade.

### Seleção automática de board — 0.0.93

A kext seleciona os dados da placa pelo subsistema PCI, sem cadastrar cada fabricante no C++ ou adicionar personalidades ao `Info.plist`. O firmware é escolhido separadamente, pelo chip e revisão de ROM suportados: **QCA6174 hw3.2** e **QCA9377 hw1.1**.

Durante `make kext`, o preparador consulta os arquivos de origem e gera o catálogo que será incluído na kext. Na inicialização, a busca segue esta ordem:

1. Entrada exata de `board-2.bin` com variante OEM, quando `Ath10kBoardVariant` estiver definida na personalidade da kext.
2. Entrada exata sem variante, usando fabricante, dispositivo e subsistema PCI.
3. `board.bin` da mesma família, quando o arquivo existir na pasta de origem.
4. Erro explícito `board-profile-not-found` se nenhum board estiver disponível; o PLL não é iniciado.

O pacote atual inclui **77 chaves PCI de QCA6174** (65 sem variante e 12 variantes OEM opcionais) e **37 de QCA9377**, incluindo Killer `1a56:143a` e Lenovo `17aa:0901`. Isso indica disponibilidade dos dados, não validação de todas essas placas em hardware.

Para atualizar a cobertura, substitua `firmware/board-2.bin` (QCA6174) ou `firmware/QCA9377/hw1.0/board-2.bin` (QCA9377) e recompile. Um `board.bin` opcional deve estar na mesma pasta do respectivo `board-2.bin`. A QCA9377 já inclui esse fallback; a QCA6174 não inclui um fallback genérico. **Um board específico de outro fabricante não deve ser usado como fallback genérico.**

Variantes OEM não são adivinhadas. Chaves que exigem identificação BMI/OTP em vez de subsistema PCI são registradas como excluídas no manifesto gerado. O suporte a outras revisões de chip continua dependendo de firmware e inicialização apropriados.

O IORegistry informa `Ath10kRequestedBoardKey`, `Ath10kPreparedBoardKey`, `Ath10kBoardLookupStatus`, `Ath10kBoardCatalogEntries`, `Ath10kFirmwareProfileAvailable` e `Ath10kSelectedBoardVariant`. Para enviar o diagnóstico:

```sh
sudo sh scripts/test-qca9377.sh > ~/Desktop/ath10k-board.txt 2>&1
```

### Ath10k Connectivity é necessário

Para procurar redes e conectar ao Wi-Fi, é necessário usar o aplicativo **Ath10k Connectivity**, junto com a kext.

O aplicativo permite selecionar a rede, informar a senha, gerenciar redes conhecidas e acompanhar a conexão. A versão **1.0.0** inclui traduções em português brasileiro, inglês e espanhol.

A Ath10kMac apresenta a conexão ao macOS por meio de uma interface de rede Ethernet. A seleção das redes Wi-Fi é feita pelo **Ath10k Connectivity**, que fica na barra de menu.

### Recursos

- Busca de redes nas bandas de **2,4 GHz e 5 GHz**.
- Conexão como cliente a redes abertas e **WPA2-Personal com AES/CCMP**.
- Operação HT/VHT, incluindo **802.11n e 802.11ac**, conforme a placa e o ponto de acesso.
- Negociação de largura de canal de **20, 40 e 80 MHz**, conforme as capacidades da rede.
- Transmissão e recepção de dados, com agregação de pacotes e controle de filas.
- QoS e parâmetros **WMM/EDCA**.
- Tratamento de canais, potência e domínio regulatório.
- Recuperação da interface após o repouso, com reinicialização do hardware e reconexão pelo aplicativo.
- Informações de diagnóstico para acompanhar inicialização, firmware e estado da conexão.

O perfil desta versão é o uso como cliente Wi-Fi com redes abertas ou WPA2-Personal. **WPA3/SAE, autenticação Enterprise/EAP, AirDrop e AWDL ainda não fazem parte do suporte oferecido.** O retorno do repouso usa reinicialização e reconexão; a conexão anterior não é mantida por WoWLAN.

### Desempenho observado

Resultados informados nos testes com a **QCA6174 e a Ath10kMac 0.0.90**:

| Banda | Download | Upload |
| --- | ---: | ---: |
| **2,4 GHz** | **32,62 Mbps** | **31,23 Mbps** |
| **5 GHz** | **275,62 Mbps** | **153,03 Mbps** |

A versão **0.0.92** também foi confirmada em uso com boa velocidade e recuperação após o repouso. Os números da tabela são uma referência da máquina testada; o desempenho depende do sinal, do roteador, do canal e da conexão de internet.

### Instalação e uso

1. Obtenha a **Ath10kMac.kext** e o **Ath10k Connectivity**.
2. Instale a kext pelo método de carregamento utilizado no seu sistema e reinicie o computador.
3. Coloque o aplicativo na pasta **Aplicativos** e abra-o.
4. Use o ícone do **Ath10k Connectivity** na barra de menu para selecionar a rede e conectar.

Em sistemas que usam **OpenCore**, adicione a kext em `EFI/OC/Kexts` e registre-a em `Kernel → Add` no `config.plist`, seguindo a configuração do seu bootloader.

Para uso com o **Ath10k Connectivity 1.0.0**, utilize **macOS 13 ou posterior**. A validação de hardware descrita acima foi feita no Sequoia.

### Compilação

Requisitos:

- macOS com Xcode e as ferramentas de linha de comando.
- Python 3.
- **MacKernelSDK** na pasta `MacKernelSDK` do projeto.
- Os arquivos de firmware e de board data fornecidos com o projeto.

Na pasta do projeto, execute:

```sh
make clean
make kext
```

A kext será gerada em:

```text
build/out/Ath10kMac.kext
```

A preparação dos arquivos de firmware é realizada pelo processo de compilação. Os avisos de licença e os créditos dos componentes estão preservados nos arquivos correspondentes.

### Relatos de testes e problemas

Relatos de funcionamento em outras máquinas são bem-vindos, especialmente para a **QCA9377**.

Ao abrir uma issue, informe:

- Modelo da placa e identificação PCI.
- Versão do macOS, da kext e do Ath10k Connectivity.
- Banda utilizada e tipo de segurança da rede.
- O que aconteceu e como reproduzir.
- Se o problema ocorre ao iniciar, conectar, transferir dados ou voltar do repouso.

Se estiver usando o código-fonte, é possível coletar um diagnóstico no Terminal, a partir da pasta do projeto:

```sh
sudo sh scripts/test-runtime.sh > ~/Desktop/ath10k-runtime.txt
```

Antes de publicar o diagnóstico, remova informações pessoais, como nomes de redes, endereços MAC e endereços IP.

### Agradecimentos

Este projeto foi possível graças ao trabalho compartilhado pela comunidade:

- **[acidanthera](https://github.com/acidanthera)**, pelo **[MacKernelSDK](https://github.com/acidanthera/MacKernelSDK)**, utilizado na compilação e no desenvolvimento da kext.
- **Qualcomm / Qualcomm Atheros**, pelos drivers, firmwares e pela lógica de funcionamento do hardware que serviram de base para o projeto.
- **Linux e os desenvolvedores do [ath10k](https://wireless.docs.kernel.org/en/latest/en/users/drivers/ath10k.html)**, pelo código, documentação e lógica dos drivers. O **[ath10k do Linux v6.12](https://github.com/torvalds/linux/tree/v6.12/drivers/net/wireless/ath/ath10k)** foi a principal referência técnica das comparações.
- **[OpenIntelWireless](https://github.com/OpenIntelWireless)**, pelo **[itlwm](https://github.com/OpenIntelWireless/itlwm)** e pelo **[HeliPort](https://github.com/OpenIntelWireless/HeliPort)**, referências para drivers Wi-Fi e aplicativos de conexão no macOS.
- **[thegwchr](https://github.com/thegwchr)**, pelo **[Feixiao](https://github.com/thegwchr/Feixiao)**, estudado como referência de adaptação de drivers Wi-Fi para macOS.
- **[laobamac](https://github.com/laobamac)**, pelo **[SimpleMtkWlan](https://github.com/laobamac/SimpleMtkWlan)**, usado nas comparações de integração com o macOS, DMA, interrupções e entrega de pacotes.
- **[flany-dev](https://github.com/flany-dev)**, pelo **[RealtekRTL8822C](https://github.com/flany-dev/RealtekRTL8822C)**, referência para integração com o macOS, desempenho e recuperação da interface.
- Aos mantenedores do **[linux-firmware](https://gitlab.com/kernel-firmware/linux-firmware)** e do **[wireless-regdb](https://kernel.googlesource.com/pub/scm/linux/kernel/git/wens/wireless-regdb/)**, pelos arquivos de firmware, board data e dados regulatórios utilizados.
- **Davi**, por disponibilizar o notebook com a **QCA6174**, permitindo testar a kext em hardware real, medir o desempenho e confirmar seu funcionamento após o retorno do repouso.

Obrigado também a todos que contribuírem com testes, relatos de problemas e melhorias.

---

## English

Ath10kMac is a kernel extension (kext) for macOS, created for **Qualcomm Atheros QCA6174 and QCA9377** Wi-Fi adapters. The driver was developed in C++/IOKit, using **Linux ath10k** as a reference for protocols, hardware initialization, and firmware communication.

**QCA6174 was confirmed functional on the tested laptop with version 0.0.92, including recovery after sleep. Version 0.0.93 adds automatic board selection; this update and full QCA9377 operation still require hardware validation.**

### Compatibility

| Adapter | PCI ID | Status |
| --- | --- | --- |
| **QCA6174** | `168c:003e` | **Validated with 0.0.92 on the tested laptop**, including connection, traffic on 2.4 GHz and 5 GHz, and recovery after sleep. Automatic selection in 0.0.93 awaits hardware testing. |
| **QCA9377** | `168c:0042` | **Experimental.** Version 0.0.93 fixes missing board selection for Lenovo `17aa:0901`; full initialization, connection and sleep recovery still require confirmation. |

The project targets **macOS on Intel computers (x86_64)**. Current testing was performed on **macOS Sequoia**. The QCA6174 results apply to the laptop and networks used for testing; other adapter revisions and configurations still need community testing reports.

### Automatic board selection — 0.0.93

The kext selects board data using PCI subsystem identifiers, without adding each manufacturer to C++ or creating separate `Info.plist` personalities. Firmware selection is separate and follows the supported chip/ROM revision: **QCA6174 hw3.2** and **QCA9377 hw1.1**.

During `make kext`, the preparation script reads the source files and generates the catalog embedded in the kext. At startup, selection uses this order:

1. Exact `board-2.bin` entry with an OEM variant, when `Ath10kBoardVariant` is set in the kext personality.
2. Exact entry without a variant, using PCI vendor, device and subsystem IDs.
3. The same family's `board.bin`, when present in the source directory.
4. An explicit `board-profile-not-found` error if no board is available; PLL initialization does not begin.

The current package includes **77 QCA6174 PCI keys** (65 unqualified entries and 12 optional OEM variants) and **37 QCA9377 keys**, including Killer `1a56:143a` and Lenovo `17aa:0901`. These counts describe available data, not hardware validation of every adapter.

To update coverage, replace `firmware/board-2.bin` (QCA6174) or `firmware/QCA9377/hw1.0/board-2.bin` (QCA9377), then rebuild. An optional `board.bin` belongs alongside its family's `board-2.bin`. QCA9377 already includes this fallback; QCA6174 does not include a generic fallback. **Another manufacturer's specific board must not be used as a generic fallback.**

OEM variants are not guessed. Keys requiring BMI/OTP identification instead of PCI subsystem IDs are recorded as excluded in the generated manifest. Other chip revisions still require appropriate firmware and initialization support.

IORegistry exposes `Ath10kRequestedBoardKey`, `Ath10kPreparedBoardKey`, `Ath10kBoardLookupStatus`, `Ath10kBoardCatalogEntries`, `Ath10kFirmwareProfileAvailable` and `Ath10kSelectedBoardVariant`. Collect diagnostics with:

```sh
sudo sh scripts/test-qca9377.sh > ~/Desktop/ath10k-board.txt 2>&1
```

### Ath10k Connectivity is required

To scan for networks and connect to Wi-Fi, you must use the **Ath10k Connectivity** application together with the kext.

The application lets you select a network, enter its password, manage saved networks, and monitor the connection. Version **1.0.0** includes Brazilian Portuguese, English, and Spanish translations.

Ath10kMac exposes the connection to macOS through an Ethernet network interface. Wi-Fi networks are selected through **Ath10k Connectivity**, which runs in the menu bar.

### Features

- Network scanning on the **2.4 GHz and 5 GHz** bands.
- Client connections to open networks and **WPA2-Personal with AES/CCMP**.
- HT/VHT operation, including **802.11n and 802.11ac**, depending on the adapter and access point.
- **20, 40, and 80 MHz** channel width negotiation, depending on network capabilities.
- Data transmission and reception, with packet aggregation and queue management.
- QoS and **WMM/EDCA** parameters.
- Channel, transmit power, and regulatory domain handling.
- Interface recovery after sleep, with hardware reinitialization and reconnection through the application.
- Diagnostic information for initialization, firmware, and connection status.

This release supports Wi-Fi client operation with open or WPA2-Personal networks. **WPA3/SAE, Enterprise/EAP authentication, AirDrop, and AWDL are not currently supported.** Recovery after sleep uses reinitialization and reconnection; the previous connection is not retained through WoWLAN.

### Observed performance

Results reported during testing with the **QCA6174 and Ath10kMac 0.0.90**:

| Band | Download | Upload |
| --- | ---: | ---: |
| **2.4 GHz** | **32.62 Mbps** | **31.23 Mbps** |
| **5 GHz** | **275.62 Mbps** | **153.03 Mbps** |

Version **0.0.92** was also confirmed in use with good speeds and recovery after sleep. The figures in the table are a reference from the tested machine; performance depends on signal strength, the router, the channel, and the internet connection.

### Installation and usage

1. Obtain **Ath10kMac.kext** and **Ath10k Connectivity**.
2. Install the kext using your system's extension loading method and restart the computer.
3. Place the application in the **Applications** folder and open it.
4. Use the **Ath10k Connectivity** menu bar icon to select a network and connect.

On systems using **OpenCore**, add the kext to `EFI/OC/Kexts` and register it under `Kernel → Add` in `config.plist`, following your bootloader configuration.

To use **Ath10k Connectivity 1.0.0**, run **macOS 13 or later**. The hardware validation described above was performed on Sequoia.

### Building

Requirements:

- macOS with Xcode and its command line tools.
- Python 3.
- **MacKernelSDK** in the project's `MacKernelSDK` directory.
- The firmware and board data files supplied with the project.

From the project directory, run:

```sh
make clean
make kext
```

The kext will be generated at:

```text
build/out/Ath10kMac.kext
```

Firmware preparation is handled by the build process. Component license notices and credits are preserved in their respective files.

### Testing reports and issues

Reports from other machines are welcome, especially for the **QCA9377**.

When opening an issue, include:

- Adapter model and PCI ID.
- macOS, kext, and Ath10k Connectivity versions.
- Wi-Fi band and network security type.
- What happened and how to reproduce it.
- Whether the issue occurs during startup, connection, data transfers, or recovery after sleep.

If you are using the source code, you can collect diagnostics in Terminal from the project directory:

```sh
sudo sh scripts/test-runtime.sh > ~/Desktop/ath10k-runtime.txt
```

Before publishing diagnostics, remove personal information such as network names, MAC addresses, and IP addresses.

### Acknowledgments

This project was made possible by the community's shared work:

- **[acidanthera](https://github.com/acidanthera)**, for **[MacKernelSDK](https://github.com/acidanthera/MacKernelSDK)**, used to build and develop the kext.
- **Qualcomm / Qualcomm Atheros**, for the drivers, firmware, and hardware logic that served as the basis for this project.
- **Linux and the [ath10k](https://wireless.docs.kernel.org/en/latest/en/users/drivers/ath10k.html) developers**, for the driver code, documentation, and logic. **[Linux v6.12 ath10k](https://github.com/torvalds/linux/tree/v6.12/drivers/net/wireless/ath/ath10k)** was the main technical reference for the comparisons.
- **[OpenIntelWireless](https://github.com/OpenIntelWireless)**, for **[itlwm](https://github.com/OpenIntelWireless/itlwm)** and **[HeliPort](https://github.com/OpenIntelWireless/HeliPort)**, references for Wi-Fi drivers and connection applications on macOS.
- **[thegwchr](https://github.com/thegwchr)**, for **[Feixiao](https://github.com/thegwchr/Feixiao)**, studied as a reference for adapting Wi-Fi drivers to macOS.
- **[laobamac](https://github.com/laobamac)**, for **[SimpleMtkWlan](https://github.com/laobamac/SimpleMtkWlan)**, used in comparisons of macOS integration, DMA, interrupts, and packet delivery.
- **[flany-dev](https://github.com/flany-dev)**, for **[RealtekRTL8822C](https://github.com/flany-dev/RealtekRTL8822C)**, a reference for macOS integration, performance, and interface recovery.
- The maintainers of **[linux-firmware](https://gitlab.com/kernel-firmware/linux-firmware)** and **[wireless-regdb](https://kernel.googlesource.com/pub/scm/linux/kernel/git/wens/wireless-regdb/)**, for the firmware files, board data, and regulatory data used in this project.
- **Davi**, for providing the laptop with the **QCA6174**, allowing us to test the kext on real hardware, measure its performance, and confirm that it works after waking from sleep.

Thank you also to everyone who contributes testing, issue reports, and improvements.

