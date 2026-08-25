#!/usr/bin/env python3

import sys
import json
import requests

BASE_URL = "https://opencode.ai/zen/v1"
MODELS_URL = f"{BASE_URL}/models"
CHAT_URL = f"{BASE_URL}/chat/completions"


def get_models():
    response = requests.get(MODELS_URL, timeout=30)
    response.raise_for_status()

    data = response.json()

    return [
        model["id"]
        for model in data.get("data", [])
        if "free" in model.get("id", "").lower()
        or model.get("id", "").lower() == "big-pickle"
    ]


def show_models(models):
    print("\nModelos disponibles:\n")

    for i, model in enumerate(models, 1):
        print(f"  {i:2}. {model}")

    print()


def chat(model):
    print(f"\nModelo: {model}")
    print("Escribe 'exit' o 'quit' para salir.")
    print("-" * 60)

    messages = []

    while True:
        try:
            user_input = input("\nTú: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ("exit", "quit"):
                break

            messages.append({
                "role": "user",
                "content": user_input
            })

            response = requests.post(
                CHAT_URL,
                headers={
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "messages": messages,
                    "stream": True
                },
                stream=True,
                timeout=300
            )

            if not response.ok:
                print(
                    f"\nError HTTP {response.status_code}:\n"
                    f"{response.text}"
                )

                messages.pop()
                continue

            print("\nIA: ", end="", flush=True)

            assistant_text = ""

            for line in response.iter_lines(decode_unicode=True):

                if not line:
                    continue

                if not line.startswith("data:"):
                    continue

                raw_data = line[5:].strip()

                if raw_data == "[DONE]":
                    break

                try:
                    chunk = json.loads(raw_data)
                except json.JSONDecodeError:
                    continue

                choices = chunk.get("choices", [])

                if not choices:
                    continue

                delta = choices[0].get("delta", {})
                text = delta.get("content")

                if text:
                    print(text, end="", flush=True)
                    assistant_text += text

            print()

            messages.append({
                "role": "assistant",
                "content": assistant_text
            })

        except KeyboardInterrupt:
            print("\n")
            break

        except requests.RequestException as e:
            print(f"\nError de conexión: {e}\n")

        except Exception as e:
            print(f"\nError: {e}\n")


def main():

    try:
        models = get_models()

    except requests.RequestException as e:
        print(f"Error obteniendo los modelos: {e}")
        sys.exit(1)

    # Sin argumento: mostrar modelos gratuitos + Big Pickle
    if len(sys.argv) == 1:
        show_models(models)

        print("Uso:")
        print("  python opencode_chat.py <modelo>")
        print()
        print("Ejemplo:")
        print("  python opencode_chat.py big-pickle")

        return

    # Con argumento:
    # NO comprobamos si existe ni si es gratuito.
    model = sys.argv[1]

    chat(model)


if __name__ == "__main__":
    main()
