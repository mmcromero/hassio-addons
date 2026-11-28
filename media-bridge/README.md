# Fábrica de Ideias - Gerenciador de Mídias

Ponte interna autenticada entre o Home Assistant e o FileBrowser Quantum para organizar a cópia de trabalho do acervo Umdoislab no HD MIDIAS2.

## Segurança

- Não monta `/media`, não recebe acesso direto ao filesystem do host e não solicita privilégios.
- Não publica porta no host; a porta 8090/tcp fica disponível somente na rede interna do Home Assistant.
- Não usa Ingress. O acesso do agente é feito pelo proxy interno do Home Assistant MCP na porta 8090.
- Sem credenciais, inicia em modo seguro: health responde `configured=false`; operações respondem 503.
- Usa conta técnica não administradora do FileBrowser, com escopo único limitado à pasta final da cópia de trabalho.
- Não existe operação de exclusão definitiva. Itens podem ser movidos para quarentena.
- Movimentações aceitam apenas arquivos individuais e verificam SHA-256 antes/depois.
- A pasta dos originais no Windows permanece fora do escopo.

## Estado inicial

O add-on pode ser instalado antes da conclusão da cópia. Deixe token, escopo e chave da ponte vazios. Nesse estado, o serviço não chama o FileBrowser e não altera nenhum arquivo.

Consulte [DOCS.md](DOCS.md) para configurar a identidade técnica depois que a transferência terminar e a pasta final estiver definida.
