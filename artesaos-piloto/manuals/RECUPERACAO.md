> Desenvolvimento **0.2.0-dev.16 — UX-Loading-01**: feedback visual de espera,
> sem mudanças de autenticação/schema/regras comerciais. Nível 1 preservado.
> Nenhuma distribuição/deploy nesta entrega. Guia/testes em docs/UX-Loading-01.md.

> Desenvolvimento **0.2.0-dev.15 — PWA-01 online**: manifest/ícones de instalação,
> sem consulta/venda offline. HA-UX-001 altera apresentação da contingência; identidade
> técnica e schemas preservados. Sem distribuição/deploy neste pacote. Nível 1
> permanece vigente. Procedimento e testes em docs/PWA-01.md no repositório; estados
> e versões anteriores abaixo são históricos quando houver divergência.

> Distribuição **0.2.0-dev.14**: inclui R1.1 e ferramentas operacionais por fase;
> schemas tenant11/control4/interest2/support2/legal3 e base 0.1.23 inalterados.
> Forja principal; HA ARM64 para instalação manual. Publicação não comprova instalação.
> Nível 1: backup recomendado, sem certificação obrigatória. As notas de versões
> antigas abaixo são históricas; verificar o estado atual em docs/operacao/DISTRIBUICOES.json.

> Segurança por fase: Nível 1 recomenda backup/recuperação, sem bloquear atualização
> comum apenas por falta de certificação. Nível 2 exige evidências proporcionais à
> política aprovada. Ver docs/operacao/SEGURANCA_POR_FASE.md e operation-policy.json.
> Nenhum nível autoriza destruir/restaurar o ativo sem autorização específica.

> Versão corrente: **0.2.0-dev.13**. Ver [estabilização e convites](ESTABILIZACAO-CONVITES.md).
> Pix aceita telefone BR com DDD; confirmação/erro aparece junto ao formulário.
> Migração incremental control4; demais schemas preservados. Manuais/evidências
> de versões anteriores abaixo são históricos. Não atualizar instalações reais
> sem autorização específica e backup consistente.

> Versão corrente: **0.2.0-dev.12**. Ver [administração dinâmica](ADMINISTRACAO-DINAMICA.md).
> Migrações tenant 11/legal 3, demais schemas preservados. Backup integral inclui
> documentos, aceites e PDFs em pilot-legal.sqlite. Não fazer downgrade sobre banco
> migrado. Instruções/evidências de versões anteriores abaixo são históricas.

# Backup, restauração e recuperação — procedimento permanente

Referência 0.2.0-dev.11. Executar em instalação real apenas com autorização específica.
Backup contém dados privados e credenciais: armazenar fora da pasta servida por HTTP,
com permissão restrita e proteção de armazenamento/criptografia aprovada pelo operador.
Não publicar em Git, tickets ou pacote de distribuição. Guardar pacote/código da versão
correspondente, hash SHA-256, data e instalação de origem. HA e Debian nunca trocam dados.

## Home Assistant

Usar backup nativo com o add-on e opções incluídos; manifesto `backup: cold` solicita
parada para backup consistente. Conferir estado e conclusão no Supervisor. Guardar
separadamente pacote-fonte/identificador/origem do add-on para reconstrução. Restaurar
pelo mecanismo nativo em instalação compatível, primeiro isoladamente. Não restaurar
arquivo de pacote-fonte como se fosse backup HA. Ver HOME-ASSISTANT.md.

## Debian — backup frio com o helper entregue

Na raiz estável da instalação, com permissão de ler data/config e operar Docker:

```sh
python3 manage.py backup --output /CAMINHO-PRIVADO/backup-novo.tar.gz
sha256sum /CAMINHO-PRIVADO/backup-novo.tar.gz
```

Destino deve ser novo, fora da pasta da instalação. O helper para somente o serviço
`artesao` desse projeto, copia data/config/.env/release.json e reinicia se ele estava
rodando. Não faz cópia quente, não reemite código, não altera esquema nem apaga dados.
Códigos temporários são excluídos. Uma falha do comando não é backup aprovado: não
usar arquivo incompleto, conservar o erro sanitizado e confirmar retorno do serviço.
Credenciais OAuth/contatos cifrados dependem das chaves no data: copiar só SQLite
individual não basta. Não copiar volume entre HA/Debian para tentar recuperar acesso.

## Debian — restauração em pasta nova, sem sobrescrever

Parar e obter autorização antes de promover uma restauração real. Preservar a
instalação e eventuais operações posteriores ao backup. Na pasta do pacote:

```sh
sha256sum /CAMINHO-PRIVADO/backup-novo.tar.gz
python3 manage.py restore --archive /CAMINHO-PRIVADO/backup-novo.tar.gz --target /CAMINHO-PRIVADO/restauracao-nova
```

O destino **não pode existir**. O helper rejeita links, caminhos absolutos/`..`,
dispositivos, duplicatas e conteúdo inesperado antes de extrair. Arquivos ficam
privados, sem confiar em IDs de dono do tar. Não inicia serviço nem promove a cópia.
O operador deve conferir dono UID/GID esperado e permissões antes de montar o volume;
se a extração foi como root, corrigir dono apenas na nova cópia autorizada, não em
dados de outra instalação. Usar pacote/compose da versão correspondente.

Validar a cópia com um processo de teste isolado e URL/porta própria, sem expor dados
privados; conferir integridade de todos os SQLite e autenticação. SQLite deve ser
aberto pelo runtime compatível, sem editar SQL. Conferir que sessões, empresa/logo,
convites/chaves e registros comerciais foram preservados. Só promover após resultado
aprovado. Preparar diretório novo de códigos 0700 com dono do processo se necessário;
emitir recuperação pelo console quando autorizado, nunca reutilizar códigos antigos.

## Atualização interrompida, falha de processo e downgrade

Primeiro preservar /data, configurações e logs sem tokens/cookies. Não apagar banco,
WAL ou chave para “destravar”; não fazer `docker compose down -v`. Reinício tenta a
recuperação transacional SQLite. Migrations comuns usam checksums/transações e recusam
schema futuro/histórico alterado. Bancos de tenant podem migrar sob demanda ao abrir.
Se falhar, não insistir em código antigo contra schema novo. Guardar cópia consistente
e investigar com versão/commit e erro sanitizado. Código antigo só volta com backup
completo compatível e escolha explícita sobre operações posteriores ao backup.

## Recuperação de autenticação

HA: preservar Google e allowlist administrativa nas opções; verificar conta, audiência,
callback, cookies e origem HTTPS. Não aplicar setup/senha Debian. Debian: emitir
`recovery-code` pelo console e usar `/admin/recover`, conforme DEBIAN.md; sucesso
revoga sessões administrativas sem apagar usuários ou negócio. Configuração de rede
ou Google real só pode ser alterada em intervenção separada autorizada.

## Exercício periódico

No Nível 2, conforme política aprovada: backup protegido, restauração isolada,
integridade/FKs, sessão/configuração e operação comercial sintética, reinício e
registro dos resultados. No Nível 1, recomendar esse exercício sem torná-lo bloqueio de atualização comum.
A existência de um arquivo não comprova recuperação.
C2 valida dados sintéticos; restauração nativa do Supervisor e hardware real permanecem
pendentes da primeira homologação autorizada.

## Evidências e retorno controlado por imagem

Estados independentes: arquivo criado; integridade verificada; cópia externa
verificada; restauração isolada testada; recuperação operacional comprovada.
`operations.py check-backup --archive /BACKUP` testa extração temporária/SQLite e
chaves exigidas por registros existentes; não comprova login/decifragem funcional.
Não modifica produção. Uma saída estrutural aprovada não autoriza apply.

Após testar de fato a recuperação isolada e a cópia externa, o operador registra
fora do Git um atestado JSON do backup exato: `archiveSha256`, `backupCreatedAt` e `testedAt` (ISO UTC),
`operator` (identificador operacional), `externalCopyVerified: true`,
`operationalRecoveryProven: true`, e descrição local dos testes/provas.
No Nível 2, o helper exige correspondência de hash e idade do backup dentro de
maxBackupAgeHours da política aprovada; a referência anterior fixa de 24 horas
foi substituída pela política por fase. Isso é
atestação explícita do operador, **não comprovação automática ou assinatura digital**.
Não criar atestado verdadeiro por mera existência de arquivo.

private-codes é usado por local-admin-console.ts para códigos temporários de
ativação/recuperação, com validade de 30 minutos/uso único. O banco guarda hashes e
estado administrativo; chaves duráveis ficam em data/. Excluir os arquivos de
código do backup é intencional e já testado em validate-distribution-tools.py.
Não foi inspecionado conteúdo real do Forja: se houver outros arquivos nesse
volume, classificar com o operador antes de considerar cobertura suficiente.
Restaurar diretório de códigos vazio, 0700/UID correto; emitir código novo pelo
console autorizado quando necessário. Não imprimir nem versionar códigos.

Após apply, o recibo privado informa o comando de retorno:
`python3 operations.py --root /srv/artesao-digital-app rollback --record
/INSTALACAO/.operations/update-ID/deployment.json --approve-code-only`.
Retorna somente à imagem preservada e à declaração anterior, sem restaurar dados.
Bloqueia se a imagem atual não corresponder à tentativa ou se schemas divergirem.
Preservar contêiner guardião, recibos, override e backups até aprovação operacional.
Após o comando verificar collect, healthcheck, logs sanitizados e autenticação.
Não declarar rollback funcional aprovado apenas pelo aceite do Compose.

Pacote-fonte, runtime/labels, backup, atestado, ID da imagem e recibo de implantação
são evidências distintas. Imagem presente somente no HD do Forja não é cópia externa.
O retorno que exige restauração de dados permanece operação separada autorizada.

Após atualizações por imagem, usar o manage.py do pacote atualizado com
`--root /srv/artesao-digital-app` para incluir a declaração ativa no próximo backup.
O helper histórico da instalação pode não conhecer .operations/active-release.json.
Guardar também recibos operacionais e pacotes/imagens fora do servidor; o backup de
dados não inclui automaticamente imagens Docker nem a seleção Compose de retorno.
