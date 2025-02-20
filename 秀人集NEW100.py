import os
import aiohttp
import asyncio
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO
import json
from datetime import datetime
from urllib.parse import urlparse


url = "http://25.xy02.my/new.html"
parsed_url = urlparse(url)
base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
path_url = parsed_url.path
# 全局配置
MAX_RETRIES = 10  # 最大重试次数
RETRY_DELAY = 10  # 重试等待时间（秒）
MAX_CONCURRENT_DOWNLOADS = 100  # 最大并发下载数

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
        path_url = (article_link[:article_link.find('/', 1) + 1])

        # 提取海报地址
        poster_img = article.find('img', class_='waitpic')
        poster_url = base_url + poster_img['src'] if poster_img and poster_img.get('src') else None

        # 添加到结果列表
        articles_info.append({
            'article_url': article_url,
            'poster_url': poster_url,
            'path_url': path_url
        })

    return articles_info


# 3. 提取当前页面的图片 URL
def extract_image_urls(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    image_urls = [
        base_url + img['src']
        for img in soup.find_all('img')
        if img.get('src') and (img['src'].startswith('/uploadfile/') or img['src'].startswith('/UploadFile/')) and img.get('alt') and img.get('title')
    ]
    return image_urls


# 4. 异步下载图片并保存为 JPG 格式
async def download_image(session, img_url, save_path, retries=MAX_RETRIES, article_title='', article_url='', index=None):
    for attempt in range(retries):
        try:
            async with session.get(img_url, timeout=5) as response:
                if response.status == 200:
                    content = await response.read()
                    # 将图片从 WebP 转换为 JPG
                    img = Image.open(BytesIO(content))
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                    img.save(save_path, 'JPEG')
                    return True
                elif response.status == 404:
                    return 404
                else:
                    # print(f"{article_title} {article_url} 下载图片 {index} {img_url} 失败: 状态码 {response.status}")
                    return False
        except Exception as e:
            if attempt < retries - 1:
                await asyncio.sleep(RETRY_DELAY)  # 增加等待时间
            else:
                # print(f"{article_title} {article_url} 下载图片 {index} {img_url} 失败: {e}")
                return False
    return False


# 5. 提取文章标题
def extract_article_title(html_content,path_url):
    soup = BeautifulSoup(html_content, 'html.parser')
    tag_text = soup.find('a', href=f'{path_url}').text
    title_tag = soup.find('title')
    if title_tag:
        article_title = title_tag.text.strip().replace(" - - XiuRen", "").replace(f"{tag_text}第", "")
    else:
        article_title = "未知标题"
    return article_title,tag_text


# 6. 异步获取所有页面的图片地址（确保顺序）
async def get_all_image_urls(session, article_url):
    image_urls = []
    current_page = 0
    batch_size = 30  # 每批次处理的页面数量

    # 获取第一页的内容，并解析分页总数
    first_page_content = await fetch_page(session, article_url)
    if not first_page_content:
        return image_urls,batch_size  # 如果第一页无法获取，直接返回空列表

    # 解析分页总数
    soup = BeautifulSoup(first_page_content, 'html.parser')
    pagination_div = soup.find('div', class_='page')
    if pagination_div:
        pagination_links = pagination_div.find_all('a')
        if len(pagination_links)>1:
            # 最后一个链接是“下页”，倒数第二个链接是最后一页的页码
            max_pages = int(pagination_links[-2].text)
        else:
            max_pages = 1  # 如果没有分页链接，说明只有一页
    else:
        max_pages = 1  # 如果没有分页 div，说明只有一页

    # print(f"解析到分页总数: {max_pages}")
    batch_size = batch_size if batch_size < max_pages else max_pages
    while current_page < max_pages:
        tasks = []
        page_indices = []  # 记录当前批次的页码

        # 生成当前批次的页面任务
        for _ in range(batch_size):
            if current_page == 0:
                page_link = article_url  # 第一页链接
            else:
                page_link = f"{article_url.replace('.html', '')}_{current_page}.html"

            tasks.append(fetch_page(session, page_link))
            page_indices.append(current_page)  # 记录页码
            current_page += 1

            if current_page >= max_pages:
                break  # 如果当前页码超过最大页码，停止生成任务

        # 并发获取当前批次的页面内容
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 按照页码顺序处理结果
        for page_index, html_content in zip(page_indices, results):
            if html_content is None or isinstance(html_content, Exception):
                continue  # 如果页面不存在或请求失败，跳过处理

            # 提取当前页的图片地址
            urls = extract_image_urls(html_content)
            if not urls:
                return image_urls,max_pages  # 如果没有图片地址，停止处理后续页面

            # 将图片地址与页码关联
            image_urls.extend((page_index, url) for url in urls)

    # 按照页码排序图片地址
    image_urls.sort(key=lambda x: x[0])  # 按页码排序
    return [url for _, url in image_urls],max_pages  # 返回排序后的图片地址


# 7. 异步处理单篇文章的下载
async def process_article(session, article_info, semaphore):
    async with semaphore:  # 限制并发
        article_url = article_info['article_url']
        poster_url = article_info['poster_url']
        path_url = article_info['path_url']
        html_content = await fetch_page(session, article_url)
        if not html_content:
            print(f"无法获取文章页面: {article_url}")
            return

        article_title,tag_text = extract_article_title(html_content,path_url)

        # 创建子目录
        save_dir = os.path.join(tag_text, article_title)
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)

        # 创建 metadata 目录
        metadata_dir = os.path.join(f"{tag_text}_metadata")
        if not os.path.exists(metadata_dir):
            os.makedirs(metadata_dir)

        # 下载海报图片（0.jpg）
        poster_path = os.path.join(save_dir, "0.jpg")
        if poster_url and not os.path.exists(poster_path):
            print(f"开始下载{article_title} {article_url} 海报: {poster_url}")
            await download_image(session, poster_url, poster_path, article_title=article_title, article_url=article_url)

        # 获取所有图片地址
        image_urls, max_pages = await get_all_image_urls(session, article_url)
        if not image_urls:
            print(f"{article_title} {article_url}: 未找到图片")
            return

        # 记录图片链接和序号
        metadata = {
            "article_title": article_title,
            "article_url": article_url,
            "images": [{"url": poster_url, "filename": "0.jpg", "status": "success"}]
        }

        # 准备图片下载任务
        download_tasks = []
        for idx, img_url in enumerate(image_urls):
            img_name = f"{idx + 1}.jpg"  # 图片命名从 1 开始
            save_path = os.path.join(save_dir, img_name)

            # 检查图片是否已经存在
            if os.path.exists(save_path):
                metadata["images"].append({"url": img_url, "filename": img_name, "status": "success"})
                continue

            # 创建下载任务
            download_tasks.append(
                download_image(session, img_url, save_path, article_title=article_title, article_url=article_url, index=idx+1)
            )

        # 并发执行下载任务
        download_results = await asyncio.gather(*download_tasks, return_exceptions=True)

        # 处理下载结果
        success_count = 0
        failure_count = 0
        failed_urls = []

        for idx, result in enumerate(download_results):
            img_url = image_urls[idx]
            img_name = f"{idx + 1}.jpg"

            if result is True:
                success_count += 1
                metadata["images"].append({"url": img_url, "filename": img_name, "status": "success"})
            else:
                failure_count += 1
                failed_urls.append(img_url)
                metadata["images"].append({"url": img_url, "filename": img_name, "status": "failed"})

        # 重试失败的图片
        while failed_urls:
            retry_tasks = []
            new_failed_urls = []

            for img_url in failed_urls:
                idx = image_urls.index(img_url)
                img_name = f"{idx + 1}.jpg"
                save_path = os.path.join(save_dir, img_name)

                retry_tasks.append(
                    download_image(session, img_url, save_path, article_title=article_title, article_url=article_url, index=idx+1)
                )

            retry_results = await asyncio.gather(*retry_tasks, return_exceptions=True)

            for idx, result in enumerate(retry_results):
                img_url = failed_urls[idx]
                img_name = f"{image_urls.index(img_url) + 1}.jpg"

                if result is True:
                    success_count += 1
                    failure_count -= 1
                    metadata["images"][image_urls.index(img_url)]["status"] = "success"
                else:
                    if result != 404:
                        new_failed_urls.append(img_url)

            failed_urls = new_failed_urls

        # 保存 metadata
        metadata_path = os.path.join(metadata_dir, f"{article_title}.json")
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=4)

        # 打印下载结果
        if failure_count != 0:
            print(f"{article_title} {article_url} 海报 {poster_url} 共【{max_pages}】分页 : 成功下载 {success_count} 张图片, 失败 {failure_count} 张图片", flush=True)
        else:
            print(f"{article_title} {article_url} 海报 {poster_url} 共【{max_pages}】分页 : 成功下载 {success_count} 张图片", flush=True)


# 8. 异步主函数
async def main(start_page,end_page):
    # 使用 Semaphore 限制并发
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)
    async with aiohttp.ClientSession() as session:
        current_page = start_page
        while True:
            # 生成每一页的链接
            if current_page == 1:
                page_url = base_url + path_url
            else:
                page_url = base_url + f"{path_url}index{current_page}.html"

            # 获取当前页的文章列表
            print(f'##################### 当前处理第【{current_page}】页: {page_url} #####################\n')
            start_time = datetime.now()
            html_content = await fetch_page(session, page_url)
            if html_content is None:
                break  # 如果页面不存在，停止处理后续页面

            # 提取所有文章信息
            articles_info = extract_articles_info(html_content)
            articles_info = articles_info[:20]
            if not articles_info:
                break  # 如果没有文章信息，停止处理后续页面

            # 处理当前页的文章
            tasks = [process_article(session, info, semaphore) for info in articles_info]
            await asyncio.gather(*tasks)

            end_time = datetime.now()
            # 计算总耗时
            total_time = end_time - start_time
            print(f'本页下载耗时: {total_time}\n')
            if end_page:
                if current_page >= end_page:
                    return
            current_page += 1

if __name__ == "__main__":
    # 指定起始页，默认为 1
    start_page = 1  # 你可以根据需要修改这个值
    end_page = 1
    asyncio.run(main(start_page,end_page))