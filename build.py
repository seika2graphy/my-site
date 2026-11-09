import os
import shutil
import json
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
import markdown
from PIL import Image, ImageOps
from datetime import datetime
import html

BASE_DIR = Path(__file__).parent
HERO_PHOTOS_DIR = BASE_DIR / "hero_photos"
GALLERY_PHOTOS_DIR = BASE_DIR / "gallery_photos"
IMAGES_DIR = BASE_DIR / "images"
TEMPLATES_DIR = BASE_DIR / "templates"
NEWS_DIR = BASE_DIR / "news"
PAGES_DIR = BASE_DIR / "pages"
DATA_DIR = BASE_DIR / "data"
DIST_DIR = BASE_DIR / "dist"
SITE_TITLE = "生活の写真"

SITE_CONFIG = {
    "site_title": "生活の写真",
    "site_description": "日常の光と影、手仕事と写真記録。生活の写真のアトリエサイト。",
}

VALID_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def convert_hero_image(src_path: Path, dest_dir: Path, max_size=(1920, 1080), quality=85):
    """ヒーロー画像用：16:9を意識した長辺1920pxの表示用WebPを生成"""
    dest_dir.mkdir(parents=True, exist_ok=True)
    out_file = dest_dir / f"{src_path.stem}.webp"

    # すでに変換済みで元画像より新しければスキップ
    if out_file.exists() and out_file.stat().st_mtime > src_path.stat().st_mtime:
        return out_file.name

    with Image.open(src_path) as img:
        img = ImageOps.exif_transpose(img)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.thumbnail(max_size, Image.Resampling.LANCZOS)
        img.save(out_file, "WEBP", quality=quality, method=6)

    print(f"[Hero] Converted: {src_path.name} -> {out_file.name}")
    return out_file.name


def convert_gallery_photo(src_path: Path, dest_dir: Path, display_size=(1800, 1800), thumb_size=(640, 360), quality=82):
    """
    ギャラリー写真用：
    - 表示用: 元の縦横比を維持して長辺1800pxにリサイズ
    - サムネイル: 中央基準で 16:9 (640x360) にクロップ＆WebP化
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    stem = src_path.stem
    display_file = dest_dir / f"{stem}.webp"
    thumb_file = dest_dir / f"{stem}_thumb.webp"

    # 両方存在し元画像より新しければスキップ
    if display_file.exists() and thumb_file.exists():
        src_mtime = src_path.stat().st_mtime
        if display_file.stat().st_mtime > src_mtime and thumb_file.stat().st_mtime > src_mtime:
            return {
                "stem": stem,
                "filename": display_file.name,
                "display": display_file.name,
                "thumb": thumb_file.name,
                "title": stem.replace("-", " ").replace("_", " ")
            }

    with Image.open(src_path) as img:
        img = ImageOps.exif_transpose(img)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        # 1. 表示用 (Display)
        img_display = img.copy()
        img_display.thumbnail(display_size, Image.Resampling.LANCZOS)
        img_display.save(display_file, "WEBP", quality=quality, method=6)

        # 2. 16:9 サムネイル用 (Thumb)
        img_thumb = ImageOps.fit(img, thumb_size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
        img_thumb.save(thumb_file, "WEBP", quality=quality - 5, method=6)

    print(f"[Gallery 16:9] Converted: {src_path.name} -> {display_file.name}, {thumb_file.name}")
    return {
        "stem": stem,
        "filename": display_file.name,
        "display": display_file.name,
        "thumb": thumb_file.name,
        "title": stem.replace("-", " ").replace("_", " ")
    }


def load_media_data():
    """映像（YouTube）と音（SoundCloud）の定義リストをロード（なければ空リスト）"""
    DATA_DIR.mkdir(exist_ok=True)
    
    videos_file = DATA_DIR / "videos.json"
    audios_file = DATA_DIR / "audios.json"

    gallery_videos = []
    if videos_file.exists():
        try:
            gallery_videos = json.loads(videos_file.read_text(encoding="utf-8"))
        except Exception:
            gallery_videos = []

    gallery_audios = []
    if audios_file.exists():
        try:
            gallery_audios = json.loads(audios_file.read_text(encoding="utf-8"))
        except Exception:
            gallery_audios = []

    return gallery_videos, gallery_audios


def parse_markdown(file_path):
    content = file_path.read_text(encoding="utf-8")
    meta = {}
    lines = content.splitlines()
    body_lines = []
    is_body = False

    for line in lines:
        if not is_body:
            if line.strip() == "":
                is_body = True
                continue
            if ":" in line:
                key, val = line.split(":", 1)
                meta[key.strip().lower()] = val.strip()
        else:
            body_lines.append(line)

    body_html = markdown.markdown(
        "\n".join(body_lines),
        extensions=["tables", "fenced_code"]
    )
    
    slug = file_path.stem
    return {
        "slug": slug,
        "title": meta.get("title", slug),
        "date": meta.get("date", ""),
        "image": meta.get("image", ""),
        "body": body_html,
    }


def generate_feed(articles):
    """お知らせ記事を購読可能な Atom フィード (feed.xml) として出力する"""
    base_url = "https://seika2graphy.life"
    feed_updated = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")

    xml_lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<feed xmlns="http://www.w3.org/2005/Atom">',
        f'  <title>{SITE_TITLE}</title>',
        f'  <subtitle>{SITE_CONFIG.get("site_description", "")}</subtitle>',
        f'  <link href="{base_url}/feed.xml" rel="self" type="application/atom+xml"/>',
        f'  <link href="{base_url}/" rel="alternate" type="text/html"/>',
        f'  <id>{base_url}/</id>',
        f'  <updated>{feed_updated}</updated>',
        f'  <author>',
        f'    <name>{SITE_TITLE}</name>',
        f'  </author>'
    ]

    for art in articles[:15]:
        slug = art.get("slug")
        title = html.escape(art.get("title", ""))
        article_url = f"{base_url}/news/{slug}.html"
        
        raw_date = art.get("date", "")
        if raw_date:
            try:
                dt = datetime.strptime(raw_date, "%Y-%m-%d")
                published_str = dt.strftime("%Y-%m-%dT09:00:00+09:00")
            except ValueError:
                published_str = feed_updated
        else:
            published_str = feed_updated

        body_content = art.get("body", "")

        xml_lines.append('  <entry>')
        xml_lines.append(f'    <title>{title}</title>')
        xml_lines.append(f'    <link href="{article_url}" rel="alternate" type="text/html"/>')
        xml_lines.append(f'    <id>{article_url}</id>')
        xml_lines.append(f'    <published>{published_str}</published>')
        xml_lines.append(f'    <updated>{published_str}</updated>')
        xml_lines.append(f'    <content type="html"><![CDATA[{body_content}]]></content>')
        xml_lines.append('  </entry>')

    xml_lines.append('</feed>')

    feed_content = "\n".join(xml_lines)
    (DIST_DIR / "feed.xml").write_text(feed_content, encoding="utf-8")
    print(f"Generated feed.xml with {min(len(articles), 15)} entries.")


def generate_sitemap(articles):
    """固定ページとお知らせ記事を網羅した sitemap.xml を生成する"""
    base_url = "https://seika2graphy.life"
    today = datetime.now().strftime("%Y-%m-%d")

    urls = [
        {"loc": f"{base_url}/", "lastmod": today, "changefreq": "weekly", "priority": "1.0"},
        {"loc": f"{base_url}/pages/about.html", "lastmod": today, "changefreq": "monthly", "priority": "0.8"},
        {"loc": f"{base_url}/pages/gallery.html", "lastmod": today, "changefreq": "weekly", "priority": "0.9"},
        {"loc": f"{base_url}/news/", "lastmod": today, "changefreq": "weekly", "priority": "0.8"},
    ]

    for article in articles:
        slug = article.get("slug")
        lastmod = article.get("date", today)
        urls.append({
            "loc": f"{base_url}/news/{slug}.html",
            "lastmod": lastmod,
            "changefreq": "monthly",
            "priority": "0.6"
        })

    xml_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    ]

    for item in urls:
        xml_lines.append("  <url>")
        xml_lines.append(f"    <loc>{item['loc']}</loc>")
        xml_lines.append(f"    <lastmod>{item['lastmod']}</lastmod>")
        xml_lines.append(f"    <changefreq>{item['changefreq']}</changefreq>")
        xml_lines.append(f"    <priority>{item['priority']}</priority>")
        xml_lines.append("  </url>")

    xml_lines.append("</urlset>")

    sitemap_content = "\n".join(xml_lines)
    (DIST_DIR / "sitemap.xml").write_text(sitemap_content, encoding="utf-8")
    print(f"Generated sitemap.xml with {len(urls)} URLs.")


def build():
    DIST_DIR.mkdir(exist_ok=True)
    NEWS_DIST_DIR = DIST_DIR / "news"
    NEWS_DIST_DIR.mkdir(exist_ok=True)
    PAGES_DIST_DIR = DIST_DIR / "pages"
    PAGES_DIST_DIR.mkdir(exist_ok=True)
    HERO_PHOTOS_DIR.mkdir(exist_ok=True)
    GALLERY_PHOTOS_DIR.mkdir(exist_ok=True)
    IMAGES_DIR.mkdir(exist_ok=True)
    PAGES_DIR.mkdir(exist_ok=True)
    
    shutil.copy(BASE_DIR / "style.css", DIST_DIR / "style.css")

    # 1. TOP画像（WebP変換）
    dist_hero = DIST_DIR / "hero_photos"
    dist_hero.mkdir(parents=True, exist_ok=True)
    hero_photos = []
    if HERO_PHOTOS_DIR.exists():
        for f in sorted(HERO_PHOTOS_DIR.iterdir()):
            if f.suffix.lower() in VALID_EXTENSIONS:
                webp_name = convert_hero_image(f, dist_hero)
                hero_photos.append(webp_name)

# 2. ギャラリー画像（写真 ＆ 藍 の仕分け ＋ 新しい順に並び替え）
    dist_gallery = DIST_DIR / "gallery_photos"
    dist_gallery.mkdir(parents=True, exist_ok=True)
    gallery_photos = []
    gallery_indigo = []

    if GALLERY_PHOTOS_DIR.exists():
        # サブディレクトリも含めて探索（reverse=True で新しい連番・名前が先頭になるように降順ソート）
        for f in sorted(GALLERY_PHOTOS_DIR.rglob("*"), reverse=True):
            if f.is_file() and f.suffix.lower() in VALID_EXTENSIONS:
                if "_thumb" in f.name:
                    continue
                photo_data = convert_gallery_photo(f, dist_gallery)

                # フォルダ名またはファイル名に 'indigo' や '藍' が含まれていれば「藍」に分類
                is_indigo = "indigo" in f.parent.name.lower() or "indigo" in f.stem.lower() or "藍" in f.stem
                if is_indigo:
                    gallery_indigo.append(photo_data)
                else:
                    gallery_photos.append(photo_data)

    # 3. 映像・音の外部データ読み込み
    gallery_videos, gallery_audios = load_media_data()

    # 4. その他画像（ロゴなど）コピー
    dist_images = DIST_DIR / "images"
    dist_images.mkdir(parents=True, exist_ok=True)
    if IMAGES_DIR.exists():
        shutil.copytree(IMAGES_DIR, dist_images, dirs_exist_ok=True)

    # 5. 記事・固定ページの読み込み
    articles = [parse_markdown(f) for f in NEWS_DIR.glob("*.md")]
    articles.sort(key=lambda x: x["date"], reverse=True)
    pages = [parse_markdown(f) for f in PAGES_DIR.glob("*.md")]

    # 6. テンプレート描画
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
    
    # 6-1. お知らせ個別詳細
    article_template = env.get_template("article.html")
    for art in articles:
        (NEWS_DIST_DIR / f"{art['slug']}.html").write_text(
            article_template.render(**SITE_CONFIG, article=art), encoding="utf-8"
        )

    # 6-2. アーカイブ一覧ページ（/news/index.html）
    news_list_template = env.get_template("news_list.html")
    news_list_html = news_list_template.render(
        site_title=SITE_TITLE,
        articles=articles
    )
    (NEWS_DIST_DIR / "index.html").write_text(news_list_html, encoding="utf-8")

    # 6-3. トップページ（最新5件）
    index_template = env.get_template("index.html")
    index_html = index_template.render(
        **SITE_CONFIG,
        hero_photos=hero_photos,
        articles=articles[:5]
    )
    (DIST_DIR / "index.html").write_text(index_html, encoding="utf-8")

    # 6-4. 固定ページ（pages/配下）
    page_template = env.get_template("page.html")
    gallery_template = env.get_template("gallery.html")
    
    for p in pages:
        if p["slug"] == "gallery":
            html = gallery_template.render(
                **SITE_CONFIG,
                page=p,
                gallery_photos=gallery_photos,
                gallery_indigo=gallery_indigo,
                gallery_videos=gallery_videos,
                gallery_audios=gallery_audios
            )
        else:
            html = page_template.render(**SITE_CONFIG, page=p)
        (PAGES_DIST_DIR / f"{p['slug']}.html").write_text(html, encoding="utf-8")

    # 7. sitemap.xml & feed.xml の自動生成
    generate_sitemap(articles)
    generate_feed(articles) 

    # GitHub Pages用：Jekyllの自動処理を無効化する空ファイルを生成
    (DIST_DIR / ".nojekyll").touch()

    print(
        f"ビルド完了！ "
        f"写真: {len(gallery_photos)}枚 / 藍: {len(gallery_indigo)}枚 / "
        f"映像: {len(gallery_videos)}件 / 音: {len(gallery_audios)}件 / "
        f"ヒーロー: {len(hero_photos)}枚 / お知らせ: {len(articles)}件"
    )


if __name__ == "__main__":
    build()