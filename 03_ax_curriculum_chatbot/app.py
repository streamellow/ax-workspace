#!/usr/bin/env python3
"""
AX 교육 커리큘럼 설계 챗봇
실행: py app.py
"""

import os
import sys
import subprocess

# ── 패키지 자동 설치 (py 런처로 실행 시 venv 패키지가 없을 때 대비) ──
REQUIRED = ["openai", "python-dotenv", "rich"]

def _ensure_packages():
    import importlib.util
    pkg_map = {"python-dotenv": "dotenv"}   # install name → import name
    missing = []
    for pkg in REQUIRED:
        import_name = pkg_map.get(pkg, pkg)
        if importlib.util.find_spec(import_name) is None:
            missing.append(pkg)
    if missing:
        print(f"[설치 중] 누락 패키지: {', '.join(missing)}")
        subprocess.check_call([sys.executable, "-m", "pip", "install", *missing, "-q"])
        print("[완료] 패키지 설치 완료. 앱을 시작합니다.\n")

_ensure_packages()

from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich import box
from prompts import SYSTEM_PROMPT, INITIAL_GREETING

load_dotenv()
console = Console()

# ── 상수 ────────────────────────────────────────────────────────
MODELS = {
    "1": "gpt-4o",
    "2": "gpt-4o-mini",
    "3": "gpt-4-turbo",
    "4": "gpt-3.5-turbo",
}

QUICK_PROMPTS = {
    "1": "대기업 임원 15명을 대상으로 AI 경영 전략과 디지털 트랜스포메이션 방향성을 이해하는 반나절(4시간) 교육 커리큘럼을 만들어주세요.",
    "2": "IT 비전공 일반 직원 30명을 위한 ChatGPT 실무 활용 1일 교육 커리큘럼을 만들어주세요. 문서 작성, 이메일, 데이터 분석 업무에 바로 쓸 수 있는 내용으로 구성해주세요.",
    "3": "Python 기초를 아는 개발자 20명을 위한 AI 서비스 개발 5일 과정 커리큘럼을 만들어주세요. OpenAI API, 프롬프트 엔지니어링, RAG, 에이전트 구축까지 포함해주세요.",
    "4": "HR 담당자 10명을 위한 AI 기반 채용 혁신 2일 교육 커리큘럼을 만들어주세요.",
}


# ── 유틸 ────────────────────────────────────────────────────────
def clear():
    os.system("cls" if os.name == "nt" else "clear")


def print_header():
    console.print(Panel(
        "[bold white]🎓  AX 교육 커리큘럼 설계 챗봇[/bold white]\n"
        "[dim]기업 맞춤형 AI Transformation 교육과정을 설계합니다 | 20년 경력 IT·AI 교육 전문가[/dim]",
        style="bold blue",
        border_style="blue",
        padding=(1, 4),
    ))


def print_commands():
    t = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    t.add_column(style="cyan bold", width=12)
    t.add_column(style="white")
    t.add_row("/help",  "명령어 목록 보기")
    t.add_row("/quick", "예시 주제 빠른 선택")
    t.add_row("/save",  "대화 내용 파일로 저장")
    t.add_row("/reset", "대화 초기화")
    t.add_row("/model", "AI 모델 변경")
    t.add_row("/exit",  "종료")
    console.print(Panel(t, title="[bold]명령어[/bold]", border_style="dim"))


def select_model() -> str:
    t = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    t.add_column(style="cyan", width=4)
    t.add_column(style="white")
    for k, v in MODELS.items():
        t.add_row(k, v)
    console.print(t)
    choice = Prompt.ask("모델 번호 선택", choices=list(MODELS), default="1")
    return MODELS[choice]


def quick_select() -> str | None:
    t = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    t.add_column(style="cyan", width=4)
    t.add_column(style="yellow bold", width=22)
    t.add_column(style="white")
    rows = [
        ("임원 AI 전략 (4h)",   QUICK_PROMPTS["1"][:50] + "…"),
        ("실무자 ChatGPT (1일)", QUICK_PROMPTS["2"][:50] + "…"),
        ("개발자 AI 개발 (5일)", QUICK_PROMPTS["3"][:50] + "…"),
        ("HR 채용 혁신 (2일)",  QUICK_PROMPTS["4"][:50] + "…"),
    ]
    for i, (title, preview) in enumerate(rows, 1):
        t.add_row(str(i), title, preview)
    console.print(Panel(t, title="[bold]예시 주제[/bold]", border_style="yellow"))
    choice = Prompt.ask("번호 선택 (취소: Enter)", default="")
    return QUICK_PROMPTS.get(choice)


def save_conversation(messages: list[dict], model: str):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = Path(f"ax_curriculum_{ts}.txt")
    lines = [
        "=" * 60,
        "  AX 교육 커리큘럼 설계 챗봇 대화 기록",
        f"  저장 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"  모델: {model}",
        "=" * 60, "",
    ]
    for m in messages:
        prefix = "🤖 어시스턴트" if m["role"] == "assistant" else "👤 사용자"
        lines += [f"[{prefix}]", m["content"], ""]
    path.write_text("\n".join(lines), encoding="utf-8")
    console.print(f"[green]저장 완료:[/green] {path.resolve()}")


def get_response(client: OpenAI, model: str, messages: list[dict]) -> str:
    api_msgs = [{"role": "system", "content": SYSTEM_PROMPT}] + messages
    response = client.chat.completions.create(
        model=model,
        messages=api_msgs,
        temperature=0.7,
        max_tokens=4096,
    )
    return response.choices[0].message.content


# ── 메인 루프 ───────────────────────────────────────────────────
def main():
    clear()
    print_header()

    # API 키 확인
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        console.print("[yellow]OPENAI_API_KEY 환경변수가 없습니다.[/yellow]")
        api_key = Prompt.ask("OpenAI API 키를 입력하세요", password=True)
    if not api_key:
        console.print("[red]API 키가 없으면 실행할 수 없습니다.[/red]")
        sys.exit(1)

    client = OpenAI(api_key=api_key)

    # 모델 선택
    console.print("\n[bold]사용할 모델을 선택하세요:[/bold]")
    model = select_model()
    console.print(f"[green]모델:[/green] {model}\n")

    # 명령어 안내
    print_commands()

    # 초기 인사말
    console.print("\n[dim]──────────────────────────────────────────[/dim]")
    console.print("[bold blue]🤖 어시스턴트[/bold blue]\n")
    console.print(Markdown(INITIAL_GREETING))
    console.print("[dim]──────────────────────────────────────────[/dim]\n")

    messages: list[dict] = [{"role": "assistant", "content": INITIAL_GREETING}]

    # 대화 루프
    while True:
        try:
            user_input = Prompt.ask("[bold green]👤 나[/bold green]").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]종료합니다.[/dim]")
            break

        if not user_input:
            continue

        cmd = user_input.lower()

        if cmd in ("/exit", "/quit", "/q"):
            if Confirm.ask("종료하시겠습니까?"):
                break
            continue

        if cmd == "/help":
            print_commands()
            continue

        if cmd == "/reset":
            if Confirm.ask("대화를 초기화하시겠습니까?"):
                messages = [{"role": "assistant", "content": INITIAL_GREETING}]
                clear()
                print_header()
                console.print("\n[green]대화가 초기화되었습니다.[/green]\n")
            continue

        if cmd == "/save":
            save_conversation(messages, model)
            continue

        if cmd == "/model":
            console.print("\n[bold]모델을 변경하세요:[/bold]")
            model = select_model()
            console.print(f"[green]모델 변경:[/green] {model}\n")
            continue

        if cmd == "/quick":
            selected = quick_select()
            if selected:
                user_input = selected
                console.print(f"\n[dim]선택된 프롬프트:[/dim] {user_input[:80]}…\n")
            else:
                continue

        # GPT 호출
        messages.append({"role": "user", "content": user_input})
        try:
            with console.status("[bold blue]응답 생성 중...[/bold blue]"):
                answer = get_response(client, model, messages)
            console.print("\n[dim]──────────────────────────────────────────[/dim]")
            console.print("[bold blue]🤖 어시스턴트[/bold blue]\n")
            console.print(Markdown(answer))
            console.print("[dim]──────────────────────────────────────────[/dim]\n")
            messages.append({"role": "assistant", "content": answer})
        except Exception as e:
            console.print(f"[red]오류: {e}[/red]")
            messages.pop()

    console.print("[dim]대화를 종료합니다. 감사합니다![/dim]")


if __name__ == "__main__":
    main()
