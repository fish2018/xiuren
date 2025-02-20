import os
import aiohttp
import asyncio
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO
import logging

# 基础 URL
base_url = "http://25.xy02.my"

# 重试次数
MAX_RETRIES = 3

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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
                    logging.error(f"无法访问页面 {url}: 状态码 {response.status}")
                    return None
        except Exception as e:
            if attempt < retries - 1:
                await asyncio.sleep(2)  # 等待一段时间后重试
            else:
                logging.error(f"请求页面 {url} 失败: {e}")
                return None

# 2. 提取当前页面的图片 URL
def extract_image_urls(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    image_urls = [
        base_url + img['src']
        for img in soup.find_all('img')
        if img.get('src') and img['src'].startswith('/uploadfile/') and img.get('alt') and img.get('title')
    ]
    return image_urls

# 3. 异步下载图片并保存为 JPG 格式
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
        except Exception as e:
            if attempt < retries - 1:
                await asyncio.sleep(2)  # 等待一段时间后重试
            else:
                logging.error(f"下载图片 {img_url} 失败: {e}")
                return False
    return False

# 4. 提取文章标题
def extract_article_title(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    title_tag = soup.find('title')
    if title_tag:
        article_title = title_tag.text.strip().replace("XiuRen秀人网第", "").replace(" - - XiuRen", "")
    else:
        article_title = "未知标题"
    return article_title

# 5. 异步获取所有页面的图片地址
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

# 6. 异步处理单篇文章的下载
async def process_article(session, article_link):
    article_url = base_url + article_link
    html_content = await fetch_page(session, article_url)
    if not html_content:
        logging.error(f"无法获取文章页面: {article_url}")
        return

    article_title = extract_article_title(html_content)

    # 创建子目录
    save_dir = os.path.join("photos", article_title)
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)

    # 打印开始下载信息
    logging.info(f"{article_title} {article_url}: 开始下载图片")

    # 获取所有图片地址
    image_urls = await get_all_image_urls(session, article_url)
    if not image_urls:
        logging.warning(f"{article_title} {article_url}: 未找到图片")
        return

    # 并发下载图片
    tasks = []
    for idx, img_url in enumerate(image_urls):
        img_name = f"{idx + 1}.jpg"  # 图片命名从 1 开始
        save_path = os.path.join(save_dir, img_name)

        # 检查图片是否已经存在
        if os.path.exists(save_path):
            logging.info(f"图片 {save_path} 已存在，跳过下载")
            continue

        tasks.append(download_image(session, img_url, save_path))

    # 等待所有下载任务完成
    results = await asyncio.gather(*tasks)
    success_count = sum(results)
    failure_count = len(results) - success_count

    # 打印下载结果
    logging.info(f"{article_title} {article_url}: 成功下载 {success_count} 张图片, 失败 {failure_count} 张图片")

# 7. 异步主函数
async def main():
    # 示例文章链接列表
    article_links = [
        "/Taste/16708.html",
        # 添加更多文章链接
    ]

    async with aiohttp.ClientSession() as session:
        tasks = [process_article(session, link) for link in article_links]
        await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())