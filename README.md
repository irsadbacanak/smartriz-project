# SmarTRIZ

SmarTRIZ, TRIZ (Theory of Inventive Problem Solving — İcatçı Problem Çözme Teorisi) metodolojisini yapay zeka ile birleştiren çok-ajanlı bir mühendislik inovasyon platformudur. Sistem; bir mühendislik problemini girdi olarak alır, bunu dört aşamalı bir LLM ajan pipeline'ından geçirir ve kullanıcıya Altshuller matrisine dayalı, adım adım açıklanmış inventif çözümler sunar. Projenin ikinci katmanı ise bu pipeline'ın çıktılarını kaynak olarak kullanarak açık ağırlıklı bir modeli (Qwen2.5-7B) TRIZ'e özgü biçimde ince ayarlamak için tasarlanmış bir sentetik veri üretim ve eğitim sistemidir.

---

## İçindekiler

1. [Proje Genel Bakış](#1-proje-genel-bakış)
2. [Proje Yapısı](#2-proje-yapısı)
3. [Ortam Kurulumu](#3-ortam-kurulumu)
4. [Ajan Pipeline'ı — Çalışma Akışı](#4-ajan-pipelineı--çalışma-akışı)
5. [API](#5-api)
6. [Frontend](#6-frontend)
7. [Sentetik Veri Üretim Pipeline'ı](#7-sentetik-veri-üretim-pipelineı)
8. [Eğitim Notebook'ları](#8-eğitim-notebookları)
9. [Test](#9-test)
10. [Araçlar ve Yardımcı Scriptler](#10-araçlar-ve-yardımcı-scriptler)
11. [Veri Dosyaları](#11-veri-dosyaları)

---

## 1. Proje Genel Bakış

### TRIZ Nedir?

TRIZ, 1950'lerde Genrich Altshuller tarafından 400.000'den fazla patent analiz edilerek geliştirilen sistematik inovasyon metodolojisidir. Metodolojinin çekirdeğinde iki temel araç vardır:

- **39 Mühendislik Parametresi**: Hız, ağırlık, güvenilirlik, enerji tüketimi gibi sistemi tanımlayan değişkenler.
- **40 İnventif Prensip**: Çelişkili parametreler arasındaki gerilimi çözmek için patent literatüründen damıtılmış evrensel stratejiler.
- **39×39 Altshuller Çelişki Matrisi**: İyileştirmek istenen parametre ile kötüleşen parametrenin kesişim noktasında hangi prensipler kullanılması gerektiğini gösteren tablo.

SmarTRIZ bu metodolojinin tamamını otomatikleştirir: problem alır, parametreleri belirler, çelişkileri tespit eder, matristen prensip önerir ve somut bir çözüm üretir.

### Proje Kapsamı

| Bileşen | Teknoloji | Amaç |
|---------|-----------|-------|
| Ajan pipeline'ı | LangGraph + Ollama | TRIZ analizini 4 adımda çalıştırır |
| REST API | FastAPI | Pipeline'ı HTTP üzerinden servis eder |
| SSE akışı | Server-Sent Events | Her ajan tamamlandığında frontend'e bildirir |
| Frontend | React 19 + Vite | Canlı ajan görselleştirmesi ve sonuç arayüzü |
| Veri üretimi | DeepSeek-V4-Pro + Qwen2.5-72B | Teacher-Judge örüntüsüyle sentetik eğitim verisi |
| Fine-tuning | Qwen2.5-7B (SFT + DPO) | TRIZ'e özel açık ağırlıklı model |

---

## 2. Proje Yapısı

```text
smartriz-project/
├── src/smartriz/
│   ├── agents/                  # LangGraph ajan pipeline'ı
│   │   ├── graph.py             # StateGraph tanımı ve akış mantığı
│   │   ├── state.py             # TRIZState TypedDict
│   │   ├── prompts.py           # Her ajan için sistem ve kullanıcı istemleri
│   │   └── llm_client.py        # Ollama LLM bağlantısı
│   ├── api/
│   │   └── main.py              # FastAPI uygulama ve endpoint'ler
│   ├── data_generation/
│   │   ├── config.py            # Model adları, fiyatlandırma, yollar, CostTracker
│   │   ├── pipeline/
│   │   │   ├── teacher.py       # DeepSeek-V4-Pro'ya async çağrılar
│   │   │   ├── judge.py         # Qwen2.5-72B ile kalite değerlendirmesi
│   │   │   ├── orchestrator.py  # Ana yönetici; teacher → judge → sweep zinciri
│   │   │   ├── sweeps.py        # 7 aşamalı kalite süzgeci
│   │   │   ├── seeds.py         # Seed zamanlayıcı ve yük dengeleme
│   │   │   ├── extractor.py     # <think> bloğundan reasoning_chain çıkartma
│   │   │   ├── build_dpo_pairs.py # Kabul/ret çiftlerinden DPO dataset'i oluşturma
│   │   │   └── io.py            # JSONL okuma/yazma, işlenmiş anahtar yönetimi
│   │   ├── prompts/
│   │   │   ├── self_instruct.py    # Varyasyon üretimi
│   │   │   ├── evol_deepening.py   # İkincil çelişki ekleme
│   │   │   ├── evol_constraint.py  # Gerçek dünya kısıtı ekleme
│   │   │   └── evol_cross_domain.py # Farklı alana transfer
│   │   └── quality/
│   │       ├── matrix.py        # Altshuller 39×39 matrisi ve doğrulama
│   │       ├── triz_kb.py       # 40 inventif prensip bilgi tabanı
│   │       └── deduplicator.py  # Cosine similarity deduplikasyonu
│   ├── core/
│   ├── models/
│   ├── evaluation/
│   └── utils/
├── tests/
│   └── test_data_generation/    # Birim testleri
├── scripts/                     # CLI araçları ve smoke test'ler
├── data/                        # Üretilen JSONL/JSON dosyaları ve bilgi tabanı
├── notebooks/                   # Google Colab eğitim notebook'ları
└── ui/                          # React + Vite frontend
```

---

## 3. Ortam Kurulumu

### Gereksinimler

- Python 3.10+
- Node.js 18+ (frontend için)
- [Ollama](https://ollama.com) (yerel LLM çalıştırmak için)
- DeepInfra API anahtarı (veri üretimi için)

### Kurulum

```bash
# 1. Python bağımlılıklarını kur
pip install -e .

# 2. Ortam değişkenlerini ayarla
cp .env.example .env
# .env dosyasına şunu ekle:
# DEEPINFRA_API_KEY=your_key_here

# 3. Ollama modelini indir (ajan pipeline'ı için)
ollama pull qwen2.5:7b-instruct

# 4. Vektör veritabanını başlat
python scripts/init_vector_db.py

# 5. Kurulumu doğrula
python scripts/check_setup.py

# 6. Frontend bağımlılıklarını kur
cd ui && npm install
```

### Ortam Değişkenleri

```bash
DEEPINFRA_API_KEY=...          # Veri üretimi için zorunlu
SMARTRIZ_LOCAL_MODEL=qwen2.5:7b-instruct  # API'nin kullandığı Ollama modeli (varsayılan)
```

---

## 4. Ajan Pipeline'ı — Çalışma Akışı

Ajan pipeline'ı, `src/smartriz/agents/graph.py` dosyasında `StateGraph` olarak tanımlanmıştır. Dört düğüm sıralı biçimde çalışır; aralarındaki tüm veri tek bir `TRIZState` TypedDict üzerinden paylaşılır.

### TRIZState

```python
class TRIZState(TypedDict, total=False):
    original_problem: str              # Kullanıcıdan alınan ham problem metni
    analysis: Optional[str]            # Problem Analyst çıktısı
    contradictions: List[str]          # Tespit edilen çelişkiler (max 3)
    contradiction_details: Optional[List[Dict]]  # improving_id, worsening_id ile
    selected_principles: List[str]     # Seçilen inventif prensipler (2-4)
    principle_applications: Optional[Dict[str, str]]  # Prensip → uygulama açıklaması
    final_solution: Optional[str]      # Nihai çözüm metni
    critic_feedback: Optional[str]     # Reflexion Critic değerlendirmesi
    iterations: int                    # Çalıştırma sayacı
    meta: Optional[Dict]               # Süre, model adı, sistem sınırı vb.
```

### Düğüm 1 — Problem Analyst

**Görevi**: Ham problem metnini TRIZ diline dönüştürür.

- Sistemin bileşenlerini ve sınırlarını tanımlar (`meta.system_boundary`).
- Mevcut mühendislik durumunu ve istenilen ideal çözümü ayrıştırır.
- Problemi etkileyen anahtar fiziksel ve teknik parametreleri listeler (`meta.key_parameters`).
- Çıktısı `analysis` alanına ve `meta` sözlüğüne yazılır.

### Düğüm 2 — Contradiction Detector

**Görevi**: Problemin içindeki teknik çelişkileri TRIZ'in 39 parametresi çerçevesinde tespit eder.

- Her çelişki için "iyileştirmek istenen parametre" ve "kötüleşen parametre" çiftini belirler.
- Parametreler hem isimle hem de 1–39 arası ID ile ifade edilir (örn. `improving_id: 9`, `worsening_id: 27`).
- En fazla 3 çelişki çıkarır; bunlar `contradictions` ve `contradiction_details` alanlarına yazılır.
- Bu ID çiftleri sonraki adımda Altshuller matrisinden prensip seçmek için kullanılır.

### Düğüm 3 — ReAct Solver

**Görevi**: Tespit edilen çelişkiler için Altshuller matrisinden inventif prensipler seçer ve somut bir çözüm üretir.

- `contradiction_details` içindeki ID çiftleri ile 39×39 matrise danışır.
- 2 ila 4 prensip seçer; her birini `#N: Prensip Adı` formatında ifade eder.
- Her prensip için probleme özgü, domain-spesifik bir uygulama açıklaması yazar (`principle_applications`).
- Tüm prensipleri birleştirerek çok adımlı, uygulanabilir bir mühendislik çözümü oluşturur (`final_solution`).

### Düğüm 4 — Reflexion Critic

**Görevi**: Üretilen çözümü TRIZ fidelity ve genel kalite açısından değerlendirir.

- Seçilen prensiplerin gerçekten çelişkiyi çözüp çözmediğini kontrol eder.
- Çözümün uygulanabilirliğini, domain tutarlılığını ve terminoloji doğruluğunu denetler.
- `critic_feedback` alanına yapılandırılmış geri bildirim yazar.
- `iterations` sayacını artırır.

### Grafik Akışı

```
[Kullanıcı problemi]
        │
        ▼
┌──────────────────┐
│  Problem Analyst │  → analysis, meta.system_boundary, meta.key_parameters
└────────┬─────────┘
         │
         ▼
┌──────────────────────┐
│ Contradiction Detector│  → contradictions, contradiction_details (improving_id, worsening_id)
└────────┬─────────────┘
         │
         ▼
┌──────────────────┐
│   ReAct Solver   │  → selected_principles, principle_applications, final_solution
└────────┬─────────┘
         │
         ▼
┌──────────────────────┐
│  Reflexion Critic    │  → critic_feedback, iterations
└──────────────────────┘
         │
         ▼
   [Tam TRIZState]
```

### Streaming Mekanizması

`stream_analysis_events()` fonksiyonu LangGraph'ın node event'lerini dinler. Her ajan tamamlandığında bir SSE (Server-Sent Events) mesajı yayınlar. Mesaj zinciri şu sıradadır:

```
agent_start (analyst)
agent_done  (analyst)  → partial state güncellenir
agent_start (detector)
agent_done  (detector) → partial state güncellenir
agent_start (solver)
agent_done  (solver)   → partial state güncellenir
agent_start (critic)
agent_done  (critic)   → partial state güncellenir
complete                → tam TRIZState gönderilir
```

Hata durumunda `error` event'i yayınlanır ve bağlantı kapatılır.

---

## 5. API

`src/smartriz/api/main.py` — FastAPI uygulaması.

### Başlatma

```bash
python scripts/run_api.py
# → http://localhost:8000
```

### Endpoint'ler

#### `GET /health`
Servis sağlık kontrolü.
```json
{"status": "ok"}
```

#### `POST /api/analyze`
Senkron analiz — tüm pipeline tamamlanınca tam `TRIZState` döner.

```bash
curl -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"problem": "Bisiklet zinciri yük altında uzuyor ama daha hafif yapılırsa kırılıyor."}'
```

Yanıt süresi yaklaşık 10–30 saniyedir (Ollama modelinin hızına bağlı).

#### `GET /api/stream`
Asenkron analiz — her ajan tamamlandığında SSE event'i yayınlar.

```bash
curl "http://localhost:8000/api/stream?problem=Bisiklet+zinciri..."
```

CORS yalnızca `http://localhost:5173` için açıktır.

---

## 6. Frontend

React 19 + Vite SPA. Routing kütüphanesi yoktur; ekran geçişleri `App.jsx` içindeki `useState` ile yönetilir.

### Başlatma

```bash
cd ui
npm run dev   # → http://localhost:5173
```

### Ekran Akışı

```
ProblemInput
    │  (form gönderilir, SSE başlar)
    ▼
AgentPipeline       ← Her ajan tamamlandığında canlı güncellenir
    │  (tüm ajanlar biter)
    ▼
┌──────────────────────────────────┐
│  ProblemSummary                  │ Orijinal problem özeti
│  ContradictionCard               │ Çelişki + TRIZ parametre ID'leri
│  PrinciplesGrid                  │ 2–4 prensip kartı + uygulama açıklamaları
│  SolutionText                    │ Nihai mühendislik çözümü
│  CriticAssessment                │ Reflexion Critic geri bildirimi
│  ReferenceMatrix                 │ Altshuller matrisi görselleştirmesi
│  ReasoningTrace                  │ Adım adım akıl yürütme zinciri
│  PrincipleDetailPanel            │ Seçili prensibin derinlemesine incelemesi
└──────────────────────────────────┘
```

### `useTrizStream` Hook'u

`ui/src/hooks/useTrizStream.js` — SSE bağlantısını ve durum makinesini yönetir.

- `EventSource` üzerinden backend'e bağlanır.
- Her `agent_done` event'inde partial `TRIZState`'i günceller.
- Durum makinesi: `idle` → `running` → `complete` | `error`
- `complete` event'inde bağlantıyı kapatır.

---

## 7. Sentetik Veri Üretim Pipeline'ı

`src/smartriz/data_generation/` — 86 seed case'ten ≥10.000 yüksek kaliteli TRIZ eğitim örneği üretir.

### Genel Akış

```
86 seed case
     │
     ▼  [Self-Instruct → 5 varyasyon]
     │  [Evol-Deepening, Evol-Constraint, Evol-Cross-Domain]
     ▼
raw_generations.jsonl
     │
     ▼  [Teacher (DeepSeek-V4-Pro) → reasoning_chain çıkartma]
     ▼
     │  [Judge (Qwen2.5-72B) → 6-kriter binary rubric]
     ▼
judged.jsonl
     │
     ▼  [Altshuller matris doğrulama]
     │  [Prensip adı hardgate]
     │  [Çelişki kopyası kontrolü]
     │  [Komplekslik etiketi validasyonu]
     ▼
matrix_validated.jsonl
     │
     ▼  [Cosine similarity deduplikasyon > 0.85]
     ▼
deduplicated.jsonl
     │
     ▼  [Pydantic şema validasyonu]
     ▼
training_dataset.json   ←  Nihai eğitim seti
rejected_dataset.jsonl  ←  Başarısız örnekler (nedenli)
borderline.jsonl        ←  BORDERLINE FAIL (kurtarma için)
```

### Üretim Yöntemleri (Teacher)

Öğretmen model olarak **DeepSeek-V4-Pro** kullanılır (DeepInfra üzerinden, maliyet: $1.40/1M token). Her seed için dört yöntem uygulanır:

| Yöntem | Açıklama |
|--------|----------|
| **Self-Instruct** | 1 seed → 5 stil/bağlam varyasyonu üretir |
| **Evol-Deepening** | Mevcut case'e ikincil bir çelişki ekler (karmaşıklığı artırır) |
| **Evol-Constraint** | Gerçek dünya kısıtı ekler (bütçe, ağırlık, sertifikasyon vb.) |
| **Evol-Cross-Domain** | Case'i farklı bir mühendislik alanına transfer eder |

Öğretmen, her LLM çağrısında `<think>` bloğu içinde açık akıl yürütme üretir. `extractor.py` bu bloğu parse ederek `reasoning_chain` alanına yazar.

### Kalite Değerlendirmesi (Judge)

Hakim model olarak **Qwen2.5-72B-Instruct** kullanılır (farklı LLM ailesi — tarafsız değerlendirme için). Her case 6 binary soru üzerinden değerlendirilir:

| Soru | İçerik |
|------|--------|
| Q1 | Prensipler kanonik TRIZ isimleriyle mi yazılmış? |
| Q2 | Tüm prensipler akıl yürütmede kullanılmış mı? |
| Q3 | Çelişki gerçekten domain'e uygun mu? |
| Q4 | Çözüm zorla uydurulmuş mu? (ters soru) |
| Q5 | Akıl yürütme domain'e özgü detaylar içeriyor mu? |
| Q6 | TRIZ terminolojisi doğru mu? |

Sonuçlar: **PASS** (kabul), **FAIL** (ret → `rejected_dataset.jsonl`), **BORDERLINE FAIL** (kısmen uygun → `borderline.jsonl`, komplekslik indirgenerek kurtarılabilir).

Eski sayısal format (0–10) da desteklenir; eşik: 7.0.

### 7 Aşamalı Kalite Süzgeci (`sweeps.py`)

| Aşama | Kontrol | Başarısızlık Durumu |
|-------|---------|---------------------|
| 1 | Self-Instruct üretimi | — |
| 2A–2C | Evol yöntemleri | — |
| 3 | `reasoning_chain` var mı? | Drop + log |
| 4 | Judge verdict: PASS mı? | FAIL → rejected, BORDERLINE → borderline |
| 5.1 | Altshuller matris hücresi boş değil mi? | Drop + log |
| 5.2 | Tüm prensip adları `TRIZ_PRINCIPLES`'da var mı? | Hardgate drop |
| 5.2b | Çelişki parent seed'den kopyalanmış mı? | Drop + log |
| 5.2c | `complexity` etiketi `{simple, medium, complex}` içinde mi? | Drop + log |
| 5.3 | Kayıt ID çakışması var mı? | Assertion hatası |
| 6 | Problem alanı cosine similarity > 0.85 mi? | Düşük skorlu drop |
| 7 | Pydantic şema validasyonu geçiyor mu? | Drop + log |

### Teknik Özellikler

- **Eşzamanlılık**: `asyncio.Semaphore(MAX_CONCURRENCY=25)` — 25 paralel teacher çağrısı
- **Retry**: Exponential backoff (429, 5xx, timeout → 2 deneme); ikinci denemede sıcaklık düşürülür (T=0.3)
- **Crash-safe**: `processed_keys.txt` checkpoint dosyası ile program yeniden başlatıldığında tamamlanan görevler atlanır
- **Maliyet takibi**: Her token sayılır, her çağrıda USD hesaplanır; `HARD_STOP_USD = 120.0` aşılırsa pipeline durur
- **Fiyatlandırma**: Teacher $1.40/1M token, Judge $0.35/1M token (DeepInfra)
- **Sıcaklıklar**: `[0.7, 0.9, 1.1, 1.3]` — her varyasyon farklı sıcaklıkta üretilir
- **Deduplikasyon modeli**: `sentence-transformers/all-MiniLM-L6-v2`, cosine threshold: 0.85

### DPO Çiftlerinin Oluşturulması

`build_dpo_pairs.py` scripti, kabul edilmiş (`training_dataset.json`) ve reddedilmiş (`rejected_dataset.jsonl`) örnekleri eşleştirerek Direct Preference Optimization için `(chosen, rejected)` çiftleri üretir.

### Çalıştırma

```bash
# Yardım
python scripts/generate_data.py --help

# Smoke test (5 seed, 1 round, hızlı doğrulama)
python scripts/generate_data.py --smoke --n 5

# Tam çalıştırma
python scripts/generate_data.py

# DPO çiftlerini oluştur
python scripts/generate_data.py --build-dpo-pairs
```

---

## 8. Eğitim Notebook'ları

`notebooks/` — Google Colab Pro'da A100 GPU ile sıralı çalıştırılır.

| # | Notebook | GPU Süresi | Çıktı |
|---|----------|-----------|-------|
| 0 | `00_dataset_analysis.ipynb` | ~10 dk | `training_dataset_clean.json`, `test_split.json` |
| 1 | `01_sft_training.ipynb` | ~4–6 saat | `checkpoints/sft-7b/merged/` |
| 2 | `02_dpo_training.ipynb` | ~1–2 saat | `checkpoints/dpo-7b/merged/` |
| 3 | `03_convert_and_eval.ipynb` | ~2–3 saat | `gguf/*.gguf`, `evaluation/results.json` |

14B model için GPU sürelerini ~2.5× çarpın ve her notebook'un config hücresinde `MODEL_SIZE = '14b'` ayarlayın.

### Notebook 00 — Dataset Analizi

- `training_dataset.json`'u yükler, duplicate ve format hatalarını temizler.
- `test_split.json`'u stratified örnekleme ile ayırır.
- `training_dataset_clean.json`'u sonraki notebook'lar için kaydeder.
- Yeniden çalıştırılırsa temizlenmiş dosya zaten varsa atlar (idempotent).

### Notebook 01 — Supervised Fine-Tuning (SFT)

- Temel model: `Qwen/Qwen2.5-7B-Instruct`
- Yöntem: QLoRA (4-bit quantization)
- İzleme: Weights & Biases (W&B)
- Checkpoint resume: `OUTPUT_DIR` içindeki en son `checkpoint-N`'den devam eder.
- Çıktı: Merged model ağırlıkları `checkpoints/sft-7b/merged/`

### Notebook 02 — Direct Preference Optimization (DPO)

- Giriş: SFT checkpoint + `dpo_dataset.json` (chosen/rejected çiftleri)
- `dpo_dataset.json` yoksa `build_dpo_pairs.py` otomatik çalıştırılır.
- Checkpoint resume destekler.
- Çıktı: `checkpoints/dpo-7b/merged/`

### Notebook 03 — GGUF Dönüşüm ve Değerlendirme

- `llama.cpp` ile model `Q4_K_M` formatına dönüştürülür.
- DeepInfra'daki referans model ile benchmark karşılaştırması yapılır (BLEU, ROUGE, semantic similarity).
- Sonuçlar `evaluation/results.json`'a yazılır.
- `.gguf` dosyaları varsa dönüşüm atlanır; per-model skorlar varsa değerlendirme atlanır.

### Google Drive Kurulumu

Her notebook çalıştırılmadan önce Drive'da şu klasör yapısı oluşturulmalıdır:

```
MyDrive/smartriz/
└── data/
    ├── training_dataset.json       ← repo: data/training_dataset.json
    ├── rejected_dataset.jsonl      ← repo: data/rejected_dataset.jsonl
    └── borderline.jsonl            ← repo: data/borderline.jsonl
```

Notebook'larda `DRIVE_PATH = '/content/drive/MyDrive/smartriz/'` değerini güncelleyin.

### API Anahtarları

| Anahtar | Notebook | Nereden |
|---------|----------|---------|
| W&B API key | 01 | wandb.ai → User Settings → API Keys |
| DeepInfra API key | 02, 03 | deepinfra.com → API Keys |

### Eğitilmiş Modeli Ollama'ya Yükleme

```bash
# Modelfile oluştur
cat > ~/models/Modelfile-smartriz << 'EOF'
FROM ~/models/smartriz-dpo-7b-Q4_K_M.gguf
SYSTEM "You are SmarTRIZ, an expert engineering innovation assistant. Solve technical problems using TRIZ methodology. Identify the technical contradiction, select inventive principles from the Altshuller matrix, reason step by step, and propose a solution."
PARAMETER temperature 0
EOF

# Modeli kaydet
ollama create smartriz -f ~/models/Modelfile-smartriz

# Çalıştır
ollama run smartriz "Bir bisiklet zinciri yük altında uzuyor..."
```

---

## 9. Test

```bash
# Tüm testler
.venv/bin/python -m pytest -q

# Tek dosya
.venv/bin/python -m pytest tests/test_agents.py -q
```

### Test Kapsamı

| Dosya | Test Edilen |
|-------|-------------|
| `test_triz_kb.py` | 40 inventif prensip — kanonik isim validasyonu |
| `test_complexity_validator.py` | `{simple, medium, complex}` etiket kontrolü |
| `test_scheduler.py` | Seed zamanlayıcı ve yük dengeleme mantığı |
| `test_matrix_citations.py` | `reasoning_chain` içinden matris atıf çıkartma |
| `test_extractor.py` | `<think>` bloğu ve `reasoning_content` parse etme |
| `test_judge_borderline.py` | BORDERLINE FAIL işleme mantığı |
| `test_contradiction_validation.py` | Çelişki kopyası tespiti |

---

## 10. Araçlar ve Yardımcı Scriptler

| Script | Amaç |
|--------|-------|
| `scripts/run_api.py` | FastAPI sunucusunu başlatır (port 8000) |
| `scripts/run_graph_test.py` | LangGraph pipeline smoke testi |
| `scripts/generate_data.py` | Sentetik veri üretim CLI'ı |
| `scripts/check_setup.py` | Bağımlılıkları ve ortam değişkenlerini doğrular |
| `scripts/init_vector_db.py` | ChromaDB vektör veritabanını oluşturur |
| `scripts/generate_matrix_from_xls.py` | `data/triz_matrix.xls`'ten Altshuller matrisini yeniden üretir |
| `scripts/fix_dataset_ids.py` | Dataset kayıt ID tutarsızlıklarını düzeltir |
| `scripts/compare_sft_vs_dpo.py` | SFT ve DPO modeli çıktılarını karşılaştırır |

### Altshuller Matrisini Yeniden Üretme

```bash
# Matrisi XLS'ten yeniden oluştur
python scripts/generate_matrix_from_xls.py

# Güncel olup olmadığını kontrol et
python scripts/generate_matrix_from_xls.py --check
```

---

## 11. Veri Dosyaları

| Dosya | İçerik |
|-------|--------|
| `data/raw_generations.jsonl` | Teacher'ın ürettiği ham case'ler (filtre uygulanmamış) |
| `data/judged.jsonl` | Judge'ın değerlendirdiği case'ler (PASS/FAIL/BORDERLINE) |
| `data/matrix_validated.jsonl` | Altshuller matris + prensip + çelişki doğrulamasından geçmiş case'ler |
| `data/deduplicated.jsonl` | Cosine similarity deduplikasyonundan geçmiş case'ler |
| `data/training_dataset.json` | Nihai eğitim seti (Pydantic doğrulamalı) |
| `data/rejected_dataset.jsonl` | Reddedilen case'ler ve ret nedenleri |
| `data/borderline.jsonl` | BORDERLINE FAIL case'ler (kurtarma adayı) |
| `data/processed_keys.txt` | Tamamlanan görev anahtarları (crash-safe checkpoint) |
| `data/pipeline_summary.log` | Her round sonunda üretim özet istatistikleri |
| `data/knowledge/` | Seed dataset ve TRIZ bilgi tabanı dosyaları |
