import os
import httpx
from bs4 import BeautifulSoup
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("NVIDIA_API_KEY")

app = FastAPI()
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

client = AsyncOpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=api_key
)

MODEL = "meta/llama-3.1-8b-instruct"

class QueryRequest(BaseModel):
    question: str


async def search_web(query: str, max_results: int = 3):
    search_url = "https://html.duckduckgo.com/html"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }

    async with httpx.AsyncClient(timeout=15.0, headers=headers, follow_redirects=True) as browser:
        response = await browser.post(search_url, data={"q": query})
        response.raise_for_status()

        page = BeautifulSoup(response.text, "html.parser")
        results = []

        for item in page.select(".result"):
            title_tag = item.select_one("a.result__a")
            snippet_tag = item.select_one("div.result__snippet") or item.select_one("a.result__snippet")
            if not title_tag or not title_tag.get("href"):
                continue

            url = title_tag.get("href")
            title = title_tag.get_text(strip=True)
            snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""

            results.append({"source": title, "url": url, "snippet": snippet})
            if len(results) >= max_results:
                break

        enriched_results = []
        for result in results:
            try:
                page_resp = await browser.get(result["url"])
                page_resp.raise_for_status()
                page_soup = BeautifulSoup(page_resp.text, "html.parser")
                paragraphs = [p.get_text(strip=True) for p in page_soup.find_all("p") if p.get_text(strip=True)]
                content = "\n\n".join(paragraphs[:4]).strip()
            except Exception:
                content = result["snippet"] or "No preview available."

            enriched_results.append({
                "source": result["source"],
                "url": result["url"],
                "content": content
            })

    return enriched_results


@app.get("/", response_class=HTMLResponse)
async def read_index():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()


@app.post("/query")
async def query_knowledge(request: QueryRequest):
    context = await search_web(request.question)
    formatted_context = "\n\n".join([
        f"[{item['source']}]({item['url']}): {item['content']}" for item in context
    ])
    prompt = (
        "You are a knowledge navigator assistant. Answer the user's question using only the provided context excerpts. "
        "Cite the source names when relevant and keep the answer concise. If the question is not covered by the context, say that you cannot answer from the available knowledge.\n\n"
        f"Context:\n{formatted_context}\n\nQuestion: {request.question}\nAnswer:"
    )

    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "You are a helpful expert assistant."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2,
        max_tokens=300
    )

    answer = response.choices[0].message.content
    return {
        "answer": answer,
        "sources": [f"{item['source']} ({item['url']})" for item in context]
    }
