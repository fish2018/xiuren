from telethon import TelegramClient
from telethon.sessions import StringSession
import os
import shutil
import asyncio  # 引入 asyncio 模块以使用 sleep
import socks
import random

class TelegramImageDownloader:
    def __init__(self, api_id, api_hash, channel, download_directory, proxy):
        self.api_id = api_id
        self.api_hash = api_hash
        self.channel = channel
        self.download_directory = download_directory
        # 创建 Telegram 客户端
        if not proxy:
            self.client = TelegramClient(StringSession(string_session), api_id, api_hash)
        else:
            self.client = TelegramClient(StringSession(string_session), api_id, api_hash, proxy=proxy)

    def get_subdirectories(self, directory):
        # 获取指定目录下的所有子目录
        subdirs = [d for d in os.listdir(directory) if os.path.isdir(os.path.join(directory, d))]
        # print(subdirs)
        subdirs = ['6622期就是阿朱啊写真,就是阿朱啊,就是阿朱啊套图', '7062期杨晨晨写真,杨晨晨,杨晨晨套图', '7382期杨晨晨写真,杨晨晨,杨晨晨套图', 'XiaoYu画语界第464期杨晨晨写真,杨晨晨,杨晨晨套图', '7010期幼幼写真,幼幼,幼幼套图', 'MyGirl美媛馆第443期言沫写真,言沫,言沫套图', 'YouMi尤蜜荟第599期朱可儿写真,朱可儿,朱可儿套图', '6204期是小逗逗写真,是小逗逗,是小逗逗套图', '6652期是小逗逗写真,是小逗逗,是小逗逗套图', '7225期周于希写真,周于希,周于希套图', '3010期鱼子酱写真,鱼子酱,鱼子酱套图', '6135期鱼子酱写真,鱼子酱,鱼子酱套图', '6689期王雨纯写真,王雨纯,王雨纯套图', '1967期王雨纯写真,王雨纯,王雨纯套图', '6530期是小逗逗写真,是小逗逗,是小逗逗套图', '6020期是小逗逗写真,是小逗逗,是小逗逗套图', '6773期鱼子酱写真,鱼子酱,鱼子酱套图']
        return subdirs
    async def send_xiezhen(self, dirs):
        for index, dir in enumerate(dirs):
            dirname = os.path.basename(os.path.normpath(dir))
            # 图片文件路径
            image_dir = os.path.join(self.download_directory, dir)
            image_path = f'{image_dir}/0.jpg'
            image_paths = sorted(
                [os.path.join(image_dir, file) for file in os.listdir(image_dir) if file.endswith('.jpg')],
                key=lambda x: int(os.path.splitext(os.path.basename(x))[0])  # 按数字排序
            )
            zip_file_path = f'{image_dir}.zip'

            # 压缩目录
            if not os.path.exists(zip_file_path):
                shutil.make_archive(f'{image_dir}', 'zip', f'{image_dir}')

            print(f'当前发送：{index} {dirname}')
            # 发送图片作为相册
            await self.client.send_file(
                self.channel,
                file=image_paths,  # 发送多张图片
                caption=f'{dirname}',  # 消息说明
            )

            # 发送 ZIP 文件作为文档
            await self.client.send_file(
                self.channel,
                file=[image_path, zip_file_path],
                caption=f'{dirname}',
                force_document = True  # 强制将所有文件作为文档发送
            )

            # 每发送5套，等待x分钟
            if (index + 1) % 10 == 0:
                wait_time = random.randint(40, 50) * 60  # 随机等待时间 1 到 10 分钟（转换为秒）
                print(f'已发送 {index + 1} 套，等待 {wait_time} 秒...')
                await asyncio.sleep(wait_time)

    def run(self):
        dirs = self.get_subdirectories(self.download_directory)
        with self.client.start():
            self.client.loop.run_until_complete(self.send_xiezhen(dirs))

# 使用示例
if __name__ == "__main__":
    proxy = (socks.SOCKS5, '127.0.0.1', 7897)
    api_id = 6627460
    api_hash = '27a53a0965e486a2bc1b1fcde473b1c4'
    string_session = '1BVtsOKoBuznTFAiPsl6Y4H56wueob7zLqFt4LkSlTh7XVfGjCZcHoCLxfScyJSVFTS2zkD_JdwVW3DF9gzimgSZFVgvdEm9dtyQaBir3AbFF-Ou_g8imsnfjM8TPQSqon8LHVGmpk5pThcsJ3TvP9fJQ8GUldtAzMW1J0KtRVZR6SyHeqFpxXxZ55wgvLJlCZBHs_pjwbZnMByzMRmxXNhaJkkUdUoM_Chu6Fy0x1VhjJBCcoVKS1VYjiYSWReFGI0LgyNRHHlhZwq7IKUGonPTVsXsWxKcHgq9VSbCSRxCd8sfmyhpsD-zBtmsee7gPKQXX8XZl04nFjCr0LhCkdI6hVQiUN6o='
    download_directory = 'photos'
    channel = 'sicangpinjian'
    downloader = TelegramImageDownloader(api_id, api_hash, channel, download_directory, proxy)
    downloader.run()


'''
已经发完'5882期鱼子酱写真,鱼子酱,鱼子酱套图'
发送限流时'7191期周于希写真,周于希,周于希套图'，发了7部
telethon.errors.rpcerrorlist.FloodWaitError: A wait of 1702 seconds is required (caused by UploadMediaRequest)

准备发送'7129期唐安琪写真,唐安琪,唐安琪套图'，发了19部
telethon.errors.rpcerrorlist.FloodWaitError: A wait of 2199 seconds is required (caused by UploadMediaRequest)

准备发送'8459期桃妖夭写真,桃妖夭,桃妖夭套图'，发了11部
telethon.errors.rpcerrorlist.FloodWaitError: A wait of 1118 seconds is required (caused by UploadMediaRequest)

1939  9部
6541 11
'''