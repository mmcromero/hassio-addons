# Factory Runner — Operação e segurança

## Limites atuais

A versão 0.1.0-rc.1 é somente um candidato de **contenção**. Não tem
capacidade autorizada de desenvolver ou publicar, mesmo com Bearer válido.

O serviço exige `runner_auth_token` nas opções do Home Assistant com
um segredo de alta entropia (mínimo 32 caracteres). Não usar valores de exemplo
ou segredos versionados. O token autentica o cliente, mas **não autoriza**
operações em repositórios. Os fluxos n8n existentes não devem ser apontados
para este candidato sem homologação da mudança.

A porta `9876/tcp` não é publicada no host por padrão e o servidor usa
`127.0.0.1`. Não abrir a porta nem mudar o bind sem projeto de rede,
autorização e TLS/autenticação revisados. Nenhum novo valor deve ser escrito
em arquivos versionados para prover credenciais.

## Persistência e backup

O log de auditoria fica em `/data/factory-runner/audit.jsonl`.
O `/data` é o volume de dados persistente do add-on.
Não há bancos de dados nem diretórios de código Git montados em modo escrita.
A disponibilidade real do volume e permissões dependem da instalação física.

## Testes locais (sem GitHub Actions)

```sh
python3 -m unittest discover -s factory-runner/tests -p 'test_factory_runner_security.py' -v
python3 -m py_compile factory-runner/server.py factory-runner/autonomous_dev.py
sh -n factory-runner/run.sh
python3 .github/scripts/validate-addon-registry.py --addon factory-runner
```

O teste de registro exige `PyYAML` no ambiente local. Um build isolado
pode ser testado com `docker build --platform linux/arm64 factory-runner/`
após verificar os recursos disponíveis, sem fazer push nem instalar.

## Esteira e governança

- O workflow já existente `.github/workflows/validate-addons.yml` foi
  estendido com opção manual `factory-runner`; builds ARM64 não rodam no PR.
- O `main` da loja permanece inalterado até publicação especificamente
  autorizada. Apenas a `main` alimenta a loja instalada no HA.
- A política do Orquestrador exige testes, autorização canônica de Issue,
  branch, SHA e operação e proíbe force-push.
- Permanecem pendentes: execução real dos testes, build ARM64, homologação
  no Raspberry Pi, rotação coordenada dos segredos antigos e restauração
  funcional em ambiente isolado.

**Sem autorização de deploy, merge ou Actions nesta entrega.**
