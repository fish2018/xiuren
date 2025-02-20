import os
import aiohttp
import asyncio
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO
import json

# 基础 URL
base_url = "http://25.xy02.my"



# 全局配置
MAX_RETRIES = 5  # 最大重试次数
RETRY_DELAY = 10  # 重试等待时间（秒）
MAX_CONCURRENT_DOWNLOADS = 3  # 最大并发下载数


# 1. 异步获取网页源码
async def fetch_page(session, url, retries=MAX_RETRIES):
    for attempt in range(retries):
        try:
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    return await response.text()
                elif response.status == 404:
                    return None  # 不输出 404 警告
                else:
                    print(f"无法访问页面 {url}: 状态码 {response.status}")
                    return None
        except Exception as e:
            if attempt < retries - 1:
                await asyncio.sleep(RETRY_DELAY)  # 等待一段时间后重试
            else:
                print(f"请求页面 {url} 失败: {e}")
                return None
    return None


# 2. 提取文章 URL 和海报地址
def extract_articles_info(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    articles = soup.find('ul', class_='update_area_lists cl').find_all('li', class_='i_list list_n2')

    articles_info = []
    for article in articles:
        # 提取文章 URL
        article_link = article.find('a')['href']
        article_url = base_url + article_link

        # 提取海报地址
        poster_img = article.find('img', class_='waitpic')
        poster_url = base_url + poster_img['src'] if poster_img and poster_img.get('src') else None

        # 添加到结果列表
        articles_info.append({
            'article_url': article_url,
            'poster_url': poster_url
        })

    return articles_info


# 3. 提取当前页面的图片 URL
def extract_image_urls(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    image_urls = [
        base_url + img['src']
        for img in soup.find_all('img')
        if img.get('src') and img['src'].startswith('/uploadfile/') and img.get('alt') and img.get('title')
    ]
    return image_urls


# 4. 异步下载图片并保存为 JPG 格式
async def download_image(session, img_url, save_path, retries=MAX_RETRIES):
    for attempt in range(retries):
        try:
            async with session.get(img_url, timeout=10) as response:
                if response.status == 200:
                    content = await response.read()
                    # 将图片从 WebP 转换为 JPG
                    img = Image.open(BytesIO(content))
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                    img.save(save_path, 'JPEG')
                    return True
                else:
                    print(f"下载图片 {img_url} 失败: 状态码 {response.status}")
                    return False
        except Exception as e:
            if attempt < retries - 1:
                await asyncio.sleep(RETRY_DELAY)  # 增加等待时间
            else:
                print(f"下载图片 {img_url} 失败: {e}")
                return False
    return False


# 5. 提取文章标题
def extract_article_title(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    title_tag = soup.find('title')
    if title_tag:
        article_title = title_tag.text.strip().replace("XiuRen秀人网第", "").replace(" - - XiuRen", "")
    else:
        article_title = "未知标题"
    return article_title


# 6. 异步获取所有页面的图片地址
async def get_all_image_urls(session, article_url):
    image_urls = []
    current_page = 0

    while True:
        # 生成每一页的链接
        if current_page == 0:
            page_link = article_url  # 第一页链接
        else:
            page_link = f"{article_url.replace('.html', '')}_{current_page}.html"

        html_content = await fetch_page(session, page_link)
        if html_content is None:
            break  # 如果页面不存在，停止处理后续页面

        # 提取当前页的图片地址
        urls = extract_image_urls(html_content)
        if not urls:
            break  # 如果没有图片地址，停止处理后续页面

        image_urls.extend(urls)
        current_page += 1

    return image_urls


# 7. 异步处理单篇文章的下载
async def process_article(session, article_info, semaphore):
    async with semaphore:  # 限制并发
        article_url = article_info['article_url']
        poster_url = article_info['poster_url']
        html_content = await fetch_page(session, article_url)
        if not html_content:
            print(f"无法获取文章页面: {article_url}")
            return

        article_title = extract_article_title(html_content)

        # 创建子目录
        save_dir = os.path.join("photos", article_title)
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)

        # 创建 metadata 目录
        metadata_dir = os.path.join("metadata")
        if not os.path.exists(metadata_dir):
            os.makedirs(metadata_dir)

        # 下载海报图片（0.jpg）
        poster_path = os.path.join(save_dir, "0.jpg")
        if poster_url and not os.path.exists(poster_path):
            print(f"正在下载海报: {poster_url}")
            await download_image(session, poster_url, poster_path)

        # 获取所有图片地址
        image_urls = await get_all_image_urls(session, article_url)
        if not image_urls:
            print(f"{article_title} {article_url}: 未找到图片")
            return

        # 记录图片链接和序号
        metadata = {
            "article_title": article_title,
            "article_url": article_url,
            "images": [{"url": poster_url, "filename": "0.jpg", "status": "success"}]
        }

        # 下载图片
        success_count = 0
        failure_count = 0
        failed_urls = []

        for idx, img_url in enumerate(image_urls):
            img_name = f"{idx + 1}.jpg"  # 图片命名从 1 开始
            save_path = os.path.join(save_dir, img_name)

            # 检查图片是否已经存在
            if os.path.exists(save_path):
                success_count += 1
                metadata["images"].append({"url": img_url, "filename": img_name, "status": "success"})
                continue

            # 下载图片
            if await download_image(session, img_url, save_path):
                success_count += 1
                metadata["images"].append({"url": img_url, "filename": img_name, "status": "success"})
            else:
                failure_count += 1
                failed_urls.append(img_url)
                metadata["images"].append({"url": img_url, "filename": img_name, "status": "failed"})

        # 重试失败的图片
        while failed_urls:
            print(f"重试失败的图片: {len(failed_urls)} 张")
            new_failed_urls = []
            for img_url in failed_urls:
                idx = image_urls.index(img_url)
                img_name = f"{idx + 1}.jpg"
                save_path = os.path.join(save_dir, img_name)

                if await download_image(session, img_url, save_path):
                    success_count += 1
                    failure_count -= 1
                    metadata["images"][idx]["status"] = "success"
                else:
                    new_failed_urls.append(img_url)

            failed_urls = new_failed_urls

        # 保存 metadata
        metadata_path = os.path.join(metadata_dir, f"{article_title}.json")
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=4)

        # 打印下载结果
        print(f"{article_title} {article_url}: 成功下载 {success_count} 张图片, 失败 {failure_count} 张图片",
                     flush=True)


# 8. 异步主函数
async def main():
    # 获取热门文章页面
    hot_url = base_url + "/hot.html"
    async with aiohttp.ClientSession() as session:
        html_content = await fetch_page(session, hot_url)
        if not html_content:
            print("无法获取热门文章页面")
            return

        # 提取所有文章信息
        articles_info = extract_articles_info(html_content)
        if not articles_info:
            print("未找到文章信息")
            return

        # 使用 Semaphore 限制并发
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)
        tasks = [process_article(session, info, semaphore) for info in articles_info]
        await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())