# Limites e privacidade

> Este documento descreve a CLI inicial. O serviço de câmera real captura
> imagens em memória e abre endpoints autenticados conforme o
> [guia do módulo ao vivo](../arquitetura/camera-ao-vivo.md).

> Este documento descreve a CLI inicial. O servi?o de c?mera real captura
> imagens em mem?ria e abre endpoints autenticados conforme o
> [guia do m?dulo ao vivo](../arquitetura/camera-ao-vivo.md).

O sistema é uma ferramenta auxiliar. Verde representa verificação visual
satisfatória, não certificação de segurança ou autorização automática para soldar.
A inspeção física, os procedimentos da oficina e a supervisão permanecem necessários.

Este protótipo usa apenas evidências sintéticas. Não captura imagens, não reconhece
rostos, não identifica alunos e não abre serviço HTTP, WebSocket ou streaming.
Os UUIDs representam sessões operacionais; tracks são temporários e não entram
no histórico. Apenas o reconhecimento de alarme registra identificador de operador
simulado. O histórico fica em memória limitada e se perde ao encerrar o processo.

Futuras imagens de treinamento precisam de autorização institucional, regras para
menores quando aplicável, licença e retenção definidas. Não publicar imagens de
pessoas. Não armazenar vídeo ou imagem por padrão. Restrição à sala depende de
controles operacionais e de rede; somente estar conectado à LAN não comprova presença.

Nenhum GPIO é acessado e nenhuma máquina de solda é controlada. A integração
física precisa de instalação e validação profissional, interfaces elétricas
adequadas, proteção de componentes, sensor com tratamento de falhas e sinalização
que falhe sem manter o verde. Não ligar cargas incompatíveis diretamente ao GPIO.

Uma falha de escrita faz o controlador pedir verde desligado e informar
signaling_ok=false. Esse comando não comprova que uma saída física mudou:
feedback, watchdog físico e ensaios de falha são requisitos da fase de hardware.

A futura visão não poderá assegurar vedação, certificação ou adequação técnica
do respirador. Ausência de detecção ou mão oculta deve ser inconclusiva. Um único
bounding box de luva não comprova duas mãos protegidas.
