import os
import shutil
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
import markdown
from PIL import Image, ImageOps
from datetime import datetime

BASE_DIR = Path(__file__).parent
HERO_PHOTOS_DIR = BASE_DIR / "hero_photos"
GALLERY_PHOTOS_DIR = BASE_DIR / "gallery_photos"
IMAGES_DIR = BASE_DIR / "images"
TEMPLATES_DIR = BASE_DIR / "templates"
NEWS_DIR = BASE_DIR / "news"
PAGES_DIR = BASE_DIR / "pages"
DIST_DIR = BASE_DIR / "dist"
SITE_TITLE = "生活の写真"

SITE_CONFIG = {
    "site_title": "生活の写真",
    "site_description": "",
}

def process_gallery_photo(source_path, dest_path):
    """透かしなし・Exifの向き情報だけ正しく補正して保存"""
    with Image.open(source_path) as img:
        # 縦写真が横倒しにならないよう向きを自動補正
        img = ImageOps.exif_transpose(img)
        
        ext = dest_path.suffix.lower()
        if ext == ".png":
            img.save(dest_path, "PNG")
        else:
            img.convert("RGB").save(dest_path, "JPEG", quality=95)

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
    
    valid_extensions = {".jpg", ".jpeg", ".png", ".webp"}

    # 1. TOP画像コピー
    dist_hero = DIST_DIR / "hero_photos"
    # dist_hero を安全に作成（消さずに保持）
    dist_hero.mkdir(parents=True, exist_ok=True)
    if HERO_PHOTOS_DIR.exists():  # ※定義されている元の hero フォルダ変数名
        shutil.copytree(HERO_PHOTOS_DIR, dist_hero, dirs_exist_ok=True)
    shutil.copytree(HERO_PHOTOS_DIR, dist_hero, dirs_exist_ok=True)
    hero_photos = [f.name for f in HERO_PHOTOS_DIR.iterdir() if f.suffix.lower() in valid_extensions]

    # 2. ギャラリー画像（向き補正して書き出し）
    dist_gallery = DIST_DIR / "gallery_photos"
    dist_gallery.mkdir(parents=True, exist_ok=True)
    if GALLERY_PHOTOS_DIR.exists():  # ※定義されている元の gallery フォルダ変数名
        shutil.copytree(GALLERY_PHOTOS_DIR, dist_gallery, dirs_exist_ok=True)
    dist_gallery.mkdir(exist_ok=True)

    gallery_photos = []
    for f in sorted(GALLERY_PHOTOS_DIR.iterdir()):
        if f.suffix.lower() in valid_extensions:
            target_path = dist_gallery / f.name
            process_gallery_photo(f, target_path)
            gallery_photos.append({
                "filename": f.name,
                "title": f.stem.replace("-", " ").replace("_", " ")
            })

    # 3. その他画像（ロゴなど）コピー
    dist_images = DIST_DIR / "images"
    dist_images.mkdir(parents=True, exist_ok=True)
    if IMAGES_DIR.exists():
        shutil.copytree(IMAGES_DIR, dist_images, dirs_exist_ok=True)

    # 4. 記事・固定ページの読み込み
    articles = [parse_markdown(f) for f in NEWS_DIR.glob("*.md")]
    articles.sort(key=lambda x: x["date"], reverse=True)
    pages = [parse_markdown(f) for f in PAGES_DIR.glob("*.md")]

    # 5. テンプレート描画
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
    
    # お知らせ詳細
    article_template = env.get_template("article.html")
    for art in articles:
        (NEWS_DIST_DIR / f"{art['slug']}.html").write_text(
            article_template.render(**SITE_CONFIG, article=art), encoding="utf-8"
        )
    
    # 記事を日付の降順（新しい順）で並び替え
    articles.sort(key=lambda x: x["date"], reverse=True)

    # 1. アーカイブ一覧ページ（/news/ または /news/index.html）を生成
    news_list_template = env.get_template("news_list.html")
    news_dir = DIST_DIR / "news"
    news_dir.mkdir(parents=True, exist_ok=True)
    
    news_list_html = news_list_template.render(
        site_title=SITE_TITLE,
        articles=articles  # 全件を渡す
    )
    (news_dir / "index.html").write_text(news_list_html, encoding="utf-8")

    # 2. トップページ用には最新5件だけを渡す（スライス）
    index_template = env.get_template("index.html")
    index_html = index_template.render(
        site_title=SITE_TITLE,
        hero_photos=hero_photos,
        articles=articles[:5]  # ★最新5件に絞る（件数はお好みで変更OK）
    )
    (DIST_DIR / "index.html").write_text(index_html, encoding="utf-8")

    # 固定ページ（gallery のみ gallery.html）
    page_template = env.get_template("page.html")
    gallery_template = env.get_template("gallery.html")
    
    for p in pages:
        if p["slug"] == "gallery":
            html = gallery_template.render(**SITE_CONFIG, page=p, gallery_photos=gallery_photos)
        else:
            html = page_template.render(**SITE_CONFIG, page=p)
        (PAGES_DIST_DIR / f"{p['slug']}.html").write_text(html, encoding="utf-8")

    # TOPページ
    index_template = env.get_template("index.html")
    (DIST_DIR / "index.html").write_text(
        index_template.render(
            **SITE_CONFIG,
            hero_photos=hero_photos,
            articles=articles,
        ),
        encoding="utf-8"
    )
    
    # GitHub Pages用：Jekyllの自動処理を無効化する空ファイルを生成
    (DIST_DIR / ".nojekyll").touch()

    print(f"ビルド完了！ ギャラリー写真: {len(gallery_photos)}枚 / お知らせ: {len(articles)}件")

if __name__ == "__main__":
    build()
    
def generate_sitemap(articles):
    """固定ページとお知らせ記事を網羅した sitemap.xml を生成する"""
    base_url = "https://seika2graphy.life"
    today = datetime.now().strftime("%Y-%m-%d")

    # 1. 基本となる固定ページ（優先度と更新頻度）
    urls = [
        {"loc": f"{base_url}/", "lastmod": today, "changefreq": "weekly", "priority": "1.0"},
        {"loc": f"{base_url}/pages/about.html", "lastmod": today, "changefreq": "monthly", "priority": "0.8"},
        {"loc": f"{base_url}/pages/gallery.html", "lastmod": today, "changefreq": "weekly", "priority": "0.9"},
        {"loc": f"{base_url}/news/", "lastmod": today, "changefreq": "weekly", "priority": "0.8"},
    ]

    # 2. 全お知らせ個別記事を追加
    for article in articles:
        slug = article.get("slug")
        lastmod = article.get("date", today)
        urls.append({
            "loc": f"{base_url}/news/{slug}.html",
            "lastmod": lastmod,
            "changefreq": "monthly",
            "priority": "0.6"
        })

    # 3. XML形式に整形
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
    
    valid_extensions = {".jpg", ".jpeg", ".png", ".webp"}

    # 1. TOP画像コピー
    dist_hero = DIST_DIR / "hero_photos"
    dist_hero.mkdir(parents=True, exist_ok=True)
    if HERO_PHOTOS_DIR.exists():
        shutil.copytree(HERO_PHOTOS_DIR, dist_hero, dirs_exist_ok=True)
    hero_photos = [f.name for f in HERO_PHOTOS_DIR.iterdir() if f.suffix.lower() in valid_extensions]

    # 2. ギャラリー画像（向き補正して書き出し）
    dist_gallery = DIST_DIR / "gallery_photos"
    dist_gallery.mkdir(parents=True, exist_ok=True)
    if GALLERY_PHOTOS_DIR.exists():
        shutil.copytree(GALLERY_PHOTOS_DIR, dist_gallery, dirs_exist_ok=True)

    gallery_photos = []
    for f in sorted(GALLERY_PHOTOS_DIR.iterdir()):
        if f.suffix.lower() in valid_extensions:
            target_path = dist_gallery / f.name
            process_gallery_photo(f, target_path)
            gallery_photos.append({
                "filename": f.name,
                "title": f.stem.replace("-", " ").replace("_", " ")
            })

    # 3. その他画像（ロゴなど）コピー
    dist_images = DIST_DIR / "images"
    dist_images.mkdir(parents=True, exist_ok=True)
    if IMAGES_DIR.exists():
        shutil.copytree(IMAGES_DIR, dist_images, dirs_exist_ok=True)

    # 4. 記事・固定ページの読み込み
    articles = [parse_markdown(f) for f in NEWS_DIR.glob("*.md")]
    articles.sort(key=lambda x: x["date"], reverse=True)
    pages = [parse_markdown(f) for f in PAGES_DIR.glob("*.md")]

    # 5. テンプレート描画
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
    
    # 5-1. お知らせ個別詳細
    article_template = env.get_template("article.html")
    for art in articles:
        (NEWS_DIST_DIR / f"{art['slug']}.html").write_text(
            article_template.render(**SITE_CONFIG, article=art), encoding="utf-8"
        )

    # 5-2. アーカイブ一覧ページ（/news/index.html）
    news_list_template = env.get_template("news_list.html")
    news_list_html = news_list_template.render(
        site_title=SITE_TITLE,
        articles=articles  # 全件を渡す
    )
    (NEWS_DIST_DIR / "index.html").write_text(news_list_html, encoding="utf-8")

    # 5-3. トップページ（最新5件に絞る）
    index_template = env.get_template("index.html")
    index_html = index_template.render(
        **SITE_CONFIG,
        hero_photos=hero_photos,
        articles=articles[:5]  # 最新5件
    )
    (DIST_DIR / "index.html").write_text(index_html, encoding="utf-8")

    # 5-4. 固定ページ（pages/配下）
    page_template = env.get_template("page.html")
    gallery_template = env.get_template("gallery.html")
    
    for p in pages:
        if p["slug"] == "gallery":
            html = gallery_template.render(**SITE_CONFIG, page=p, gallery_photos=gallery_photos)
        else:
            html = page_template.render(**SITE_CONFIG, page=p)
        (PAGES_DIST_DIR / f"{p['slug']}.html").write_text(html, encoding="utf-8")

    # 6. sitemap.xml の自動生成 ★ここで呼び出す！
    generate_sitemap(articles)

    # GitHub Pages用：Jekyllの自動処理を無効化する空ファイルを生成
    (DIST_DIR / ".nojekyll").touch()

    print(f"ビルド完了！ ギャラリー写真: {len(gallery_photos)}枚 / お知らせ: {len(articles)}件")


if __name__ == "__main__":
    build()