# Contribuindo para o Sentix

Obrigado por considerar contribuir com este projeto! Nosso foco é análise de sentimento em finanças, com API e dashboard.

## Como contribuir
- Abra issues com descrições claras (bug, melhoria, documentação)
- Envie PRs pequenos e focados, com descrição do objetivo
- Mantenha o foco: sem integração com sistemas de trading; apenas webhooks genéricos
- Teste localmente antes de enviar (dashboard e API)

## Padrões
- Python >= 3.11
- Código limpo, type hints quando possível
- Mantenha dependências no `sentix/requirements.txt`
- Não incluir dados sensíveis, tokens, outputs (pkl/png) ou CSVs grandes no repositório

## Fluxo de trabalho sugerido
1. Fork do repositório
2. Crie um branch: `feat/minha-melhoria` ou `fix/meu-bug`
3. Faça suas alterações
4. Rode o dashboard e API localmente para validar
5. Abra PR com descrição e link para issue relacionada

## Licença
Este projeto está sob a licença MIT (veja o arquivo `LICENSE`). Ao contribuir, você concorda que suas contribuições serão licenciadas sob a MIT.