# Kokoro TTS (RU Masha + EN af_heart)

Port `8768`, bind `127.0.0.1`. O'zbekcha TTS (`8766`) va Piper (`8767`) o'zgarmagan.

| Til | Server | Model | Ovoz |
|---|---|---|---|
| uz | 8766 (`/api/tts` 8765 orqali) | vits_uzbek_finetuned.onnx | — |
| ru | 8768 | zaakirio/kokoro-ru (`kokoro-ru-v2-base.pth`) | `masha` |
| en | 8768 | hexgrad/Kokoro-82M (`kokoro-v1_0.pth`) | `af_heart` |

## Ishga tushirish / to'xtatish

```powershell
.\start_kokoro_tts.ps1          # yoki: .venv-kokoro\Scripts\python.exe kokoro_tts_server.py
```

To'xtatish: oynada `Ctrl+C`, yoki

```powershell
Stop-Process -Id (Get-NetTCPConnection -LocalPort 8768 -State Listen).OwningProcess
```

Muhit o'zgaruvchilari:

- `KOKORO_LANGS=en` yoki `ru` yoki `en,ru` (standart) — qaysi tillar yuklanadi.
- `KOKORO_SKIP_MEMCHECK=1` — xotira tekshiruvini o'chiradi (xavfli, pastga qarang).

## API

- `GET /api/health` → `ok`, `ready{ru,en}`, `voices`, `models`, `errors`, `memory_mb`, `free_commit_mb`.
- `POST /api/tts` `{"text": "...", "language": "ru"|"en", "speed": 1.0}` → `audio/wav`
  (24 kHz, mono, PCM16). Sarlavhalar: `X-TTS-Voice`, `X-TTS-Model`, `X-TTS-Duration`, `X-TTS-Elapsed`.
- Xatolar (JSON `{"ok": false, "error": "..."}`): `400` bo'sh matn / noto'g'ri til / noto'g'ri JSON,
  `413` matn > 2000 belgi, `422` talaffuz qilinadigan belgi yo'q, `503` model tayyor emas yoki
  navbat to'la (1 ta ishlayotgan + 4 ta kutayotgan so'rov), `500` inference xatosi.

Inference bitta lock ostida ketma-ket bajariladi; modellar server ishga tushganda bir marta yuklanadi.

## Xotira — MUHIM

O'lchangan (Windows, CPU): EN ~1.4 GB RSS / ~1.8 GB commit; EN+RU ~4.2 GB RSS / ~5.5 GB commit.
Ruscha qismning asosiy yuki — RUAccent (urg'u modellari + lug'at, ~2.2 GB), Kokoro modeli emas.

Bu mashinada (7.9 GB RAM, commit chegarasi 18.4 GB) `server.py` (MADLAD) o'zi ~9.9 GB commit
band qiladi. 2026-10-13 dagi testda EN+RU to'liq yuklanganda tizim commit'i tugab, 8765/8766/8767
jarayonlari yiqildi (keyin qayta ishga tushirildi). Shu sababli server har bir tilni yuklashdan
oldin bo'sh commit'ni tekshiradi (EN 2200 MB, RU 4000 MB) va yetmasa o'sha tilni yuklamaydi:
`/api/health` da `errors.ru` ko'rinadi, `/api/tts` `503` qaytaradi, frontend Piper'ga o'tadi.

Ruscha Masha barcha xizmatlar bilan birga ishlashi uchun: Windows pagefile hajmini oshirish
(≈ +6 GB) yoki RAM qo'shish kerak. Tekshirish: `free_commit_mb` ≥ 4000 bo'lganda serverni qayta ishga tushiring.

## Fayllar va manbalar

Modellar `kokoro-models\` ichida, aniq commit'dan yuklab olingan va SHA256 (HF LFS oid) bilan tekshirilgan.
Server `HF_HUB_OFFLINE=1` bilan ishlaydi — ish vaqtida internetga chiqmaydi.

| Fayl | Manba @ revision | SHA256 |
|---|---|---|
| `kokoro-ru\kokoro-ru-v2-base.pth` (327 MB) | zaakirio/kokoro-ru @ `d649c57b` | `3bbee5bc…3ca15` |
| `kokoro-ru\voices\masha.pt` | 〃 | `464d64ae…0a362` (har startda tekshiriladi) |
| `kokoro-ru\ru_g2p.py`, `config.json`, `kokoro-config.json`, `espeak-data\` (364 fayl) | 〃 | hajm bo'yicha tekshirilgan |
| `kokoro-82m\kokoro-v1_0.pth` (327 MB) | hexgrad/Kokoro-82M @ `f3ff3571` | `496dba11…1ad1e4` |
| `kokoro-82m\voices\af_heart.pt` | 〃 | `0ab5709b…2cb4ff` (har startda tekshiriladi) |

`sveta` va `dima` voicepack'lari yuklab olinmagan. RUAccent modellari (693 MB) birinchi yuklashda
`ruaccent/accentuator` (HF) dan `.venv-kokoro\Lib\site-packages\ruaccent\` ichiga tushgan.

Disk: `.venv-kokoro` 1.8 GB, `kokoro-models` 0.64 GB.

## Dependency versiyalari (`.venv-kokoro`, Python 3.12)

torch 2.14.1+cpu · kokoro 0.9.4 · misaki 0.9.4 · ruaccent 1.5.8.3 · onnxruntime 1.31.0 ·
transformers 5.19.0 · phonemizer-fork 3.3.2 · espeakng-loader 0.2.4 · spacy 3.8.16 +
en_core_web_sm 3.8.0 · numpy 2.5.4 · soundfile 0.14.0 · huggingface_hub 2.2.0 · psutil 7.2.2

## Windows'ga xos eslatma

`ru_g2p.py` JSON'ni kodirovkasiz o'qiydi va cp1251 lokalida `UnicodeDecodeError` beradi.
Muallif fayli o'zgartirilmagan; server o'zini `-X utf8` rejimida qayta ishga tushiradi.

## Litsenziyalar

- hexgrad/Kokoro-82M (model + af_heart): Apache-2.0.
- zaakirio/kokoro-ru: og'irliklar va ovozlar **OpenRAIL**, kod Apache-2.0. Ovozlar Dialogs korpusidagi
  aktyorlardan olingan. **Tijoriy foydalanish yoki tarqatishdan oldin OpenRAIL foydalanish cheklovlarini
  va Dialogs korpusi shartlarini alohida tekshirish shart** — bu yerda huquqiy tekshiruv o'tkazilmagan.
- RUAccent, misaki, espeak-ng (GPL-3.0, alohida kutubxona sifatida yuklanadi) — o'z litsenziyalariga qarang.

## Ma'lum cheklovlar

- Omograflar 100% emas (muallif: 93.8%); muhim matnda urg'uni `+` bilan emas, matnni qayta yozib boshqaring.
- Uzun matn: RU gaplar bo'yicha bo'linadi (≤510 fonema), EN ni Kokoro o'zi bo'ladi. 2000 belgi ≈ 110 s audio, ≈ 55 s generatsiya.
- Prosodiya deterministik: bir xil matn — bir xil audio.
