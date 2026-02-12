---

# Google Maps–Driven Healthcare Business Scraper (Qatar)

A real-world data extraction pipeline that discovers and enriches healthcare business listings in Qatar using **Google Maps**, **BeautifulSoup**, and **Playwright**.

Instead of relying on static directories, this project mimics how businesses are found in practice—through geo-based discovery and dynamically rendered websites.

---

## ✨ Features

* 📍 **Geo-driven business discovery** via Google Maps (SerpAPI)
* 🌐 **Hybrid scraping**

  * Static scraping with **BeautifulSoup**
  * Dynamic JavaScript rendering with **Playwright**
* 📧 Advanced email extraction

  * mailto links, schema markup, Cloudflare-protected emails
  * Obfuscated formats (e.g., `name [at] domain [dot] com`)
* 🧠 Email confidence scoring & filtering
* ⚡ Concurrent scraping with asyncio
* 📊 Clean CSV output ready for analysis

---

## 📈 Accuracy Highlights

* **Company name accuracy:** 100% (50/50)
* **Website availability:** 92% (46/50)
* **Email extraction success:** 84% (42/50)
* **Phone coverage:** 96% (48/50)
* **Address completeness:** 100% (50/50)
* **High-confidence records:** 78% (39/50)

---

## 🧰 Tech Stack

* **Python 3.10+**
* **SerpAPI** (Google Maps data)
* **BeautifulSoup4**
* **Playwright (Chromium)**
* **Asyncio**
* **Pandas**

---

## 🔐 API Key Security

This project **does NOT hard-code API keys**.

The SerpAPI key is loaded securely from environment variables.

### Set your API key

**Windows (PowerShell):**

```powershell
setx SERPAPI_KEY "your_api_key_here"
```

**Linux / macOS:**

```bash
export SERPAPI_KEY="your_api_key_here"
```

The script will fail fast if the key is missing:

```python
API_KEY = os.getenv("SERPAPI_KEY")
if not API_KEY:
    raise RuntimeError("SERPAPI_KEY not set in environment variables")
```

---

## 🚀 How to Run

### 1. Install dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Run the scraper

```bash
python main.py
```

### 3. Output

A CSV file will be generated:

```
qatar_healthcare_companies.csv
```

Columns:

* Company Name
* Website
* Email
* Phone
* Address

---

## 🧠 Why This Approach?

* Business directories are often outdated or incomplete
* Google Maps reflects **real-world business presence**
* Many contact details are hidden behind JavaScript
* Hybrid scraping dramatically improves data coverage and accuracy

This project demonstrates a **production-style scraping mindset**, not a toy example.

---

## ⚠️ Disclaimer

This project is for **educational and research purposes only**.
Always respect website terms of service and applicable data laws.

---

## 👤 Author

Built by **FAB**
Focused on real-world data engineering, automation, and scalable scraping systems.

---
