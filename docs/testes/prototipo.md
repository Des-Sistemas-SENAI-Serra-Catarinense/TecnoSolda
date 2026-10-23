# Executar e validar o protótipo

Requisito: Python >= 3.11. Nenhuma instalação de pacote é necessária.
Os comandos abaixo partem da raiz do repositório.

```sh
python ai-service/run.py --scenario fluxo --events
python ai-service/run.py --scenario perda-visibilidade --events
python ai-service/run.py --interactive --role operador --operator instrutor-teste
python -m unittest discover -s ai-service/tests -p test_safety.py -v
python -m unittest discover -s ai-service/tests -p test_cli.py -v
```

Cenários disponíveis: fluxo, perda-visibilidade, falha-camera, falha-sensor,
falha-processamento, luva-oculta, luva-ausente, troca-pessoa, quadros-expirados,
falha-sinalizacao. Todos mostram uma sessão verificada, a falha quando aplicável,
a recuperação, o retorno da tocha e uma nova sessão sem reaproveitar o respirador.

Cada linha da saída automática é JSON com estado, motivo, sessão, evidências,
cache do respirador, luzes, alarme e confirmação de sinalização. Com --events,
um objeto JSON formatado é acrescentado ao final com o histórico em memória.
Não se escreve vídeo, imagem ou histórico em disco automaticamente.

## Operação interativa

Digite retirar, depois cima três vezes e baixo três vezes. O resultado deve
chegar a CONFORME_VISUAL. Use oculto para apagar o verde e invalidar o respirador;
baixo sozinho não deve recuperá-lo. Execute cima três vezes e baixo três vezes
para revalidar. devolver encerra a sessão.

Outros comandos: luva-oculta, luva-ausente, camera-falha, sensor-falha,
processamento-falha, sinal-falha, recuperar, tick, reconhecer, eventos, sair.
O comando recuperar restaura dispositivos e evidências sintéticas; ainda é
necessário completar a sequência de confirmação.

O relógio é virtual: cada observação avança 0,2 s; tick avança 1 s sem quadro e
demonstra o watchdog. Aguardar no terminal não conta como tempo de monitoramento.
Não há câmera física ou varredura em segundo plano nesta CLI.

O perfil padrão é visitante. --role operador ou administrador permite demonstrar
reconhecimento do incidente. Essa escolha de argumento não é autenticação e
não pode ser usada como controle de acesso em um serviço publicado.

## Cobertura e limites dos testes

A suíte verifica sequência temporal, ordem respirador/máscara, luvas separadas,
oclusão, mudança de pessoa, múltiplas pessoas, evidências incertas e ausentes,
sessões independentes, falhas, watchdog, repetição e reordenação de quadros,
horários inválidos, exceções e dispositivo indisponível. Exercita o atraso,
pulso, intervalo, reconhecimento autorizado e desligamento do alarme.
Inclui 1.500 passos de entradas sintéticas com semente fixa, dez cenários de CLI
e interação de terminal.

Os testes demonstram comportamento do software para entradas sintéticas.
Não medem precisão de IA, latência real de câmera, FPS, vedação do respirador,
certificação de EPI, confiabilidade elétrica ou segurança de uma instalação.
Os números de quadros e timeouts precisam ser calibrados em ensaios autorizados.
