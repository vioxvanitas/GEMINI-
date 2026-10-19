from django.shortcuts import render
import json
import os
import requests
import time
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import ensure_csrf_cookie
from pathlib import Path
from django.conf import settings
from django.http import HttpResponse


def service_worker(request):
    worker_path = (
        Path(settings.BASE_DIR)
        / "static"
        / "pwa"
        / "service-worker.js"
    )

    response = HttpResponse(
        worker_path.read_text(encoding="utf-8"),
        content_type="application/javascript"
    )

    response["Service-Worker-Allowed"] = "/"
    response["Cache-Control"] = "no-cache"

    return response


@ensure_csrf_cookie
def home(request):
    return render(request, "assistant_app/index.html")

@require_POST
def chat(request):
    api_key = os.getenv("GEMINI_API_KEY")
    model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

    if not api_key:
        return JsonResponse(
            {"error": "Gemini API key is missing. Check your .env file."},
            status=500
        )

    try:
        data = json.loads(request.body)
        prompt = data.get("prompt", "").strip()
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse(
            {"error": "Invalid request data."},
            status=400
        )

    if not prompt:
        return JsonResponse(
            {"error": "Please enter a question."},
            status=400
        )

    url = (
        "https://generativelanguage.googleapis.com/"
        f"v1beta/models/{model}:generateContent"
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ]
    }

    try:
        for attempt in range(3):
            response = requests.post(
                url,
                params={"key": api_key},
                json=payload,
                timeout=45
            )

            if response.status_code != 503 or attempt == 2:
                break

            time.sleep(2 ** attempt)

        if not response.ok:
            if response.status_code == 503:
                return JsonResponse(
                    {
                        "error": (
                            "Gemini is temporarily busy. "
                            "Please try again in a moment."
                        )
                    },
                    status=503
                )

            return JsonResponse(
                {"error": "Gemini API error: " + response.text[:500]},
                status=502
            )

        result = response.json()

        answer = result["candidates"][0]["content"]["parts"][0]["text"]

        return JsonResponse({"answer": answer})

    except requests.RequestException:
        return JsonResponse(
            {"error": "Unable to connect to Gemini. Check your internet."},
            status=502
        )

    except (KeyError, IndexError, TypeError):
        return JsonResponse(
            {"error": "Gemini returned no usable text response."},
            status=502
        )
