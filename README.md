<div align="center">

# 🤖 Master SYNC

### Bot multifuncional para comunidades Discord

<p>
  <img src="https://img.shields.io/badge/Python-3.10+-8A2BE2?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/discord.py-2.x-8A2BE2?style=for-the-badge&logo=discord&logoColor=white" />
  <img src="https://img.shields.io/badge/SQLite-3-8A2BE2?style=for-the-badge&logo=sqlite&logoColor=white" />
  <img src="https://img.shields.io/badge/Status-Em%20desenvolvimento-8A2BE2?style=for-the-badge" />
</p>

</div>

<br>

---

<br>

## 📌 Sobre o projeto

O **Master SYNC** é um bot multifuncional para Discord, desenvolvido em **Python** com `discord.py 2.x`.

A ideia do projeto é reunir em um único bot vários recursos comuns de administração, interação e segurança para comunidades Discord, como moderação, tickets, logs, economia, níveis, sorteios, boas-vindas, automoderação e painéis interativos.

O projeto utiliza uma estrutura modular com **cogs**, banco de dados **SQLite** e configurações por variáveis de ambiente.

> Este projeto ainda está em desenvolvimento. Algumas funcionalidades podem mudar, receber melhorias ou precisar de testes adicionais antes do uso em servidores públicos.

<br>

---

<br>

## 🎯 Objetivo

O objetivo do **Master SYNC** é criar uma solução prática para servidores Discord, reduzindo a necessidade de usar vários bots diferentes dentro da mesma comunidade.

Além disso, o projeto também faz parte da minha evolução como desenvolvedor, praticando conceitos importantes como:

* Organização de código
* Modularização
* Persistência de dados
* Tratamento de erros
* Integração com APIs
* Boas práticas com variáveis de ambiente
* Documentação de projetos

<br>

---

<br>

## ⚙️ Principais funcionalidades

O bot foi planejado para contar com sistemas como:

* Comandos de moderação e administração
* Sistema de tickets
* Registro de eventos e ações do servidor
* Economia, cassino e ranking
* Sistema de níveis
* Sorteios
* Mensagens de boas-vindas
* Autorole
* Automoderação
* Proteção contra raid
* Comandos utilitários
* Painéis interativos com botões e menus

<br>

---

<br>

## 🧩 Estrutura do projeto

```text
MasterSync/
├── assets/          # Imagens e ícones utilizados pelo bot
├── cogs/            # Módulos e comandos do Discord
├── data/            # Configurações locais e banco criado em execução
├── database/        # Acesso ao SQLite, modelos e schema
├── scripts/         # Scripts auxiliares de administração
├── services/        # Serviços internos do projeto
├── utils/           # Funções e componentes reutilizáveis
├── .env.example     # Exemplo seguro de variáveis de ambiente
├── .gitignore       # Arquivos que não devem ir para o Git
├── config.py        # Leitura e organização das configurações
├── main.py          # Ponto de entrada do bot
└── requirements.txt # Dependências Python
```

<br>

---

<br>

## 🛠️ Tecnologias utilizadas

| Tecnologia         | Uso no projeto                  |
| ------------------ | ------------------------------- |
| **Python 3.10+**   | Linguagem principal             |
| **discord.py 2.x** | Integração com a API do Discord |
| **SQLite**         | Persistência local de dados     |
| **Pillow**         | Processamento de imagens        |
| **python-dotenv**  | Carregamento do arquivo `.env`  |

<br>

---

<br>

## 🚀 Instalação

Clone o repositório e acesse a pasta do projeto:

```bash
git clone https://github.com/os1ync/MasterSync.git
cd MasterSync
```

Crie um ambiente virtual:

```bash
python -m venv .venv
```

Ative o ambiente virtual.

No Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

No Linux ou macOS:

```bash
source .venv/bin/activate
```

Instale as dependências:

```bash
python -m pip install -r requirements.txt
```

<br>

---

<br>

## 🔐 Configuração

Crie o arquivo `.env` a partir do exemplo:

```powershell
Copy-Item .env.example .env
```

No Linux ou macOS:

```bash
cp .env.example .env
```

Depois, preencha o novo arquivo com os dados da sua aplicação no **Discord Developer Portal**.

```env
DISCORD_TOKEN=cole_o_token_do_seu_bot_aqui
COMMAND_PREFIX=/

OWNER_ID=123456789012345678
GLOBAL_ADMIN_IDS=123456789012345678

BOT_GUILD_ID=

DATABASE_PATH=data/mastersync.sqlite3
LOG_LEVEL=INFO
```

O `BOT_GUILD_ID` é opcional. Quando preenchido com o ID de um servidor de testes, os slash commands são sincronizados apenas nele. Quando vazio, a sincronização é global e pode levar mais tempo para aparecer no Discord.

Como o bot utiliza eventos de membros e conteúdo de mensagens, habilite também os intents privilegiados necessários no painel da aplicação.

> ⚠️ **Nunca publique o arquivo `.env` ou o token do bot. Se um token for exposto, gere outro imediatamente no Discord Developer Portal.**

<br>

---

<br>

## ▶️ Como iniciar

Com o ambiente virtual ativo e o `.env` configurado, execute:

```bash
python main.py
```

Na primeira execução, o projeto cria os diretórios de uso local e prepara o banco de dados SQLite.

<br>

---

<br>

## 📂 Arquivos importantes

| Arquivo ou pasta      | Responsabilidade                                                     |
| --------------------- | -------------------------------------------------------------------- |
| `main.py`             | Inicializa o bot, configura logs, carrega cogs e sincroniza comandos |
| `config.py`           | Centraliza variáveis de ambiente, caminhos e constantes              |
| `.env.example`        | Documenta as configurações sem expor dados reais                     |
| `database/schema.sql` | Define a estrutura inicial do banco de dados                         |
| `cogs/`               | Contém os recursos separados por módulo                              |
| `data/settings.json`  | Mantém valores padrão não sensíveis do projeto                       |
| `LICENSE`             | Informa as condições de uso do código                                |

<br>

---

<br>

## 🧠 Aprendizados

Este projeto faz parte do meu desenvolvimento como programador. Durante a construção do **Master SYNC**, estou praticando:

* Organização de projetos Python em módulos
* Criação de comandos slash, embeds, botões e menus
* Uso de cogs com `discord.py`
* Persistência de dados com SQLite
* Configuração segura com variáveis de ambiente
* Logs, permissões e tratamento básico de erros
* Manutenção e documentação de um projeto real

<br>

---

<br>

## 📌 Status do projeto

**Em desenvolvimento.**

O bot já possui diversos módulos implementados, mas continua passando por testes, correções e melhorias de usabilidade.

Antes de utilizá-lo em uma comunidade importante, revise as permissões do bot e teste os recursos em um servidor separado.

<br>

---

<br>

## 🗺️ Roadmap

* [ ] Ampliar os testes dos comandos e eventos
* [ ] Melhorar as configurações por servidor
* [ ] Revisar mensagens, embeds e respostas de erro
* [ ] Documentar comandos e permissões necessárias
* [ ] Fortalecer os recursos de automoderação e segurança
* [ ] Avaliar um painel web no futuro

<br>

---

<br>

## 👨‍💻 Autor

Desenvolvido por **Sync Dev** como projeto de estudo e evolução em Python.

<a href="https://github.com/os1ync">
  <img src="https://img.shields.io/badge/GitHub-os1ync-8A2BE2?style=for-the-badge&logo=github&logoColor=white" />
</a>

<br>
<br>

<div align="center">

### “Evoluindo todos os dias para transformar ideias em sistemas reais.”

</div>
