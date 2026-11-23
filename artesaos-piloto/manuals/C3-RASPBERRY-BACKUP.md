## C3 — identidade reconciliada e publicação autorizada

O operador forneceu `/config/app/f6379561_artesaos_piloto/info`: slug completo
**f6379561_artesaos_piloto**, coerente com o manifesto e o pacote. O conflito
anterior foi resolvido, sem mudar identificadores. Autorização posterior: publicar
se não houver outros bloqueios. Publicação experimental permitida; atualização,
reinício, backup/restauração e homologação reais continuam sem autorização.
As limitações físicas conhecidas permanecem; QEMU não certifica o Raspberry Pi.

# C3 — backup e recuperação específicos do Raspberry Pi 4

Alvo aarch64/HAOS 18.3/Core 2026.9.3/Supervisor 2026.09.3/SSD 480 GB, versão atual
0.1.17 informada. Procedimento preparado; nenhuma ação real executada nesta C3.
Criar/parar/restaurar/atualizar são etapas futuras, não consultas somente leitura.

## O que preservar

Backup completo nativo do HA, incluindo o add-on **pelo identificador confirmado**,
configurações/opções e dependências de acesso (proxy/certificados/configuração HA).
Conservar versão/origem/slug, hostname e pacote-fonte 0.1.17 correspondente. Não
confundir o aplicativo Fabricação e Orçamentos com Artesão Digital.

Dentro do add-on, `/data` completo contém:

- `pilot-control.sqlite`: usuários, sessões comuns/administrativas, convites,
  autorizações, fluxos, limites e detalhes cifrados dos contatos.
- `pilot-invitations.key`: chave de códigos/contatos de convites; sem ela, dados
  cifrados não são recuperáveis por simplesmente copiar o banco.
- `pilot-interest.sqlite` e `pilot-interest.key`: interessados/contatos protegidos.
- `pilot-support.sqlite`, `pilot-legal.sqlite` e `legal-config.json`, quando existente.
- `tenants/<tenant>/validation.sqlite`: empresa/logo, configurações, materiais,
  produtos/clientes/orçamentos/versões/documentos; nas novas versões, compras, lotes,
  estoque, pedidos/reservas, financeiro, vendas/sessões/consignações, pendências e
  preparos. Logo e snapshots também podem estar como BLOB/JSON nesses bancos.
- Demais arquivos/anexos presentes, além das opções do Supervisor, incluindo Google,
  allowlist e SMTP. `/data/options.json` é o caminho usado pelo processo.

Preservar WAL/SHM se existirem em uma cópia consistente; não apagá-los para corrigir
banco. Backup frio com conexões fechadas é o caminho escolhido. Não copiar só um
validation.sqlite nem restaurar volumes HA no Debian. Não regenerar chaves.
A localização física do volume é gerida pelo Supervisor: usar backup nativo e manter
a identidade completa, sem editar `/mnt/data` ou volumes Docker manualmente.

## Backup efetivo, depois de autorização

1. Registrar versão 0.1.17, identificador/origem e opções em local privado, não no Git.
   Confirmar espaço livre e destino externo; capacidade de 480 GB não prova espaço.
2. Em **Configurações → Sistema → Backups**, criar backup manual **completo**, incluindo
   o Artesão Digital e as opções. Conferir a seleção pelo nome/slug. O manifesto
   `backup: cold` pede parada durante backup; confirmar conclusão/retomada no HA.
3. Conservar cópia externa protegida, não apenas no mesmo SSD. Guardar chave/kit de
   emergência ou senha de criptografia do HA separadamente; não enviar ao assistente.
4. Conferir status, data, tamanho e componentes na UI. Calcular SHA-256 da cópia
   baixada no computador. Um hash verifica transporte, não a restauração funcional.
5. Com autorização apropriada, testar restauração em instalação HA isolada compatível,
   sem rede/callback reais, ou usar uma cópia extraída por procedimento nativo suportado.
   Este preparo não certifica o formato criptografado do backup real ainda não obtido.
6. Na cópia fria local já extraída de /data, o script entregue no repositório pode
   verificar estrutura sem escrever/migrar a origem:

```sh
python3 scripts/check-ha-backup-readonly.py --data-root /COPIA-LOCAL-FRIA/data
```

O script abre SQLite em modo somente leitura/imutável, confere integridade/FKs,
versões de migração e presença/tamanho das chaves, sem mostrar dados/segredos.
Recusa WAL com conteúdo: nesse caso, obter cópia fria íntegra, sem excluir arquivos.
Não descriptografa backup nativo HA nem comprova que contatos/sessões reais abrem;
a restauração funcional ainda precisa ser demonstrada. Não executá-lo sobre volume
ativo do servidor. Só enviar relatório sanitizado, nunca o backup ou arquivos-chave.

## Se a atualização falhar

- Parar a intervenção e preservar logs sanitizados, versão/identificador e dados.
  Não desinstalar, zerar, trocar repositório, editar SQLite ou apagar WAL/chaves.
- Falha de proxy não autoriza remover proteção Ingress nem expor 8099. Conferir
  hostname/destino existente; qualquer mudança/reinício real exige autorização.
- Se a origem e backup forem válidos, restaurar pelo fluxo nativo HA, na mesma
  identidade. Usar pacote/código anterior correspondente ao backup. Conferir opções,
  chaves, usuários/sessões, empresa e orçamentos antes de retomar operação.
- Restaurar backup completo pode afetar outros componentes do HA; avaliar impacto e
  autorização. Não executar restauração parcial improvisada para “salvar tempo”.

## Por que não fazer downgrade direto

0.1.17 antecede a fundação/migrações B1–B10. A atualização cria metadados/checksums,
consolida schema legado e adiciona estruturas comuns (tenant 10/control 3 e demais 2).
A C3 de empacotamento não adiciona outra migração, mas o salto desde 0.1.17 adiciona.
O código antigo não entende todo o modelo novo: não iniciar 0.1.17 sobre banco já
atualizado. Mesmo que o processo pareça abrir, isso não é garantia de segurança.

Retorno seguro exige **código 0.1.17 + backup completo anterior compatível**. Operações
feitas após esse backup não aparecem nele; decidir sua preservação antes de retornar.
Não sincronizar automaticamente bancos nem misturar chaves antigas/novas. Conservação
da cópia pós-falha e análise/exportação controlada podem ser necessárias, separadamente.

## Evidências desta preparação

O código publicado 0.1.17 gerou dois tenants e registros/sessões/convites sintéticos;
o backup prévio reabriu com o código original. A atualização ARM64 em QEMU preservou
registros, sessões/chaves e snapshots; a cópia pós-upgrade restaurou na versão nova.
Processo ARM emulado foi reiniciado/interrompido e recuperado em Docker isolado.
Isso não substitui backup/restauração nativos no Supervisor/Raspberry Pi reais.
