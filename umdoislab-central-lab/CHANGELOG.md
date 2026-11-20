# Central Umdoislab — LAB

## 0.4.1-rc.1 — candidata (não publicada)

- Nova instância isolada com `slug: umdoislab_central_lab`; não altera o pacote principal `umdoislab_central`.
- Código da Central vindo do PR privado #10, commit `15bd84919f996f865c98b132268da2a80d309c71`.
- Dockerfile define bloqueio obrigatório de **envio WhatsApp** para rotas manuais e automáticas.
- Identidade visual padrão do catálogo preservada por SHA.
- Worker de recuperação desativado por padrão; testes do laboratório não alteram Gateway nem Evolution.
- Publicação, instalação, boot no ARM64 e homologação ainda não executados.
