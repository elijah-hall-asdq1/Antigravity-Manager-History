
import requests
import json
import os
import sys
import datetime
import re

# 配置
REPO_OWNER = "lbjlaq"
REPO_NAME = "Antigravity-Manager"
GITHUB_API_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN") # 自动获取 Token 防止速率限制

def get_headers():
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Antigravity-Release-Monitor"
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    return headers

def normalize_text(text):
    """
    清洗文本，修复 Unicode 转义 (\\uXXXX) 和字面量换行 (\\n)
    确保 Markdown 能被正确解析
    """
    if not text:
        return ""
    
    # 1. 修复可能存在的字面量换行符 (Common in JSON dumps)
    text = text.replace('\\r\\n', '\n').replace('\\n', '\n')
    
    # 2. 修复 Unicode 转义 (e.g. \\u6838\\u5fc3 -> 核心)
    # 这种情况通常发生在之前的步骤错误地使用了 json.dumps(ensure_ascii=True)
    if '\\u' in text:
        try:
            # 只有当包含 \u 时才尝试解码
            # 使用 unicode_escape 需要先编码为 latin-1 (针对纯转义串) 或 utf-8
            # 为了安全，我们只在匹配到 unicode 模式时处理，或者尝试整体解码
            # 简单策略：如果看起来像是一堆转义符，尝试 decode
            # 注意：如果混合了正常中文和转义符，直接 decode('unicode_escape') 可能会破坏正常中文
            # 所以这里我们使用正则精确替换
            def replace_unicode(match):
                return match.group(0).encode('utf-8').decode('unicode_escape')
            
            # 匹配连续的 unicode 转义序列，例如 \u6838\u5fc3
            text = re.sub(r'(\\u[0-9a-fA-F]{4})+', replace_unicode, text)
        except Exception as e:
            # 如果转换失败，保留原样
            print(f"Warning: Failed to unescape text: {e}", file=sys.stderr)
            pass
            
    return text

def format_time_v8(iso_str):
    """Converting UTC ISO time string to Beijing Time (UTC+8)"""
    if not iso_str:
        return "Unknown"
    try:
        if iso_str.endswith('Z'):
             dt = datetime.datetime.strptime(iso_str, "%Y-%m-%dT%H:%M:%SZ")
        else:
             dt = datetime.datetime.fromisoformat(iso_str)
        dt_v8 = dt + datetime.timedelta(hours=8)
        return dt_v8.strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        return iso_str

def 获取所有版本():
    """获取所有 Release 信息"""
    releases = []
    page = 1
    while True:
        url = f"{GITHUB_API_URL}?per_page=100&page={page}"
        try:
            r = requests.get(url, headers=get_headers(), timeout=30)
            if r.status_code == 404:
                break
            r.raise_for_status()
            data = r.json()
            if not data:
                break
            releases.extend(data)
            page += 1
        except Exception as e:
            print(f"获取版本列表失败: {e}", file=sys.stderr)
            break
    return releases

def 获取最新版本():
    """获取最新 Release"""
    url = f"{GITHUB_API_URL}/latest"
    try:
        r = requests.get(url, headers=get_headers(), timeout=30)
        if r.status_code == 404:
            # 尝试获取列表第一个
            all_releases = 获取所有版本()
            if all_releases:
                return all_releases[0]
            return None
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"获取最新版本失败: {e}")
        return None

def 下载资源(assets, download_dir="."):
    """下载 Release 中的所有资源"""
    downloaded_files = []
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)
        
    for asset in assets:
        name = asset["name"]
        url = asset["browser_download_url"]
        path = os.path.join(download_dir, name)
        print(f"正在下载: {name} ...")
        
        try:
            with requests.get(url, stream=True, timeout=300) as r:
                r.raise_for_status()
                with open(path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            downloaded_files.append(name)
            print(f"下载完成: {name}")
        except Exception as e:
            print(f"下载失败 {name}: {e}")
            
    return downloaded_files

def 加载历史记录():
    if os.path.exists("history.json"):
        try:
            with open("history.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return []

def 保存历史记录(history):
    with open("history.json", "w", encoding="utf-8") as f:
        json.dump(history, f, indent=4, ensure_ascii=False)

def 生成README(history):
    # 按照发布时间倒序
    history.sort(key=lambda x: x.get("published_at", ""), reverse=True)
    
    # 获取当前时间 (北京时间)
    current_time = (datetime.datetime.utcnow() + datetime.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")
    latest = history[0] if history else {"tag_name": "Unknown", "published_at": ""}
    
    # 格式化最新版本时间
    latest_date_str = format_time_v8(latest.get("published_at", ""))
    
    md = f"""# {REPO_NAME} 自动备份监控

> [!TIP]
> 本仓库自动监控并备份 [{REPO_OWNER}/{REPO_NAME}](https://github.com/{REPO_OWNER}/{REPO_NAME}) 的 Release 版本。
> 每小时同步一次。

## 🌟 最新版本: `{latest.get('tag_name', 'N/A')}`
**更新时间**: `{latest_date_str if latest_date_str else current_time}`

## 📜 历史版本存档
| 版本 | 发布时间 | 资源文件 | 原始链接 |
| :--- | :--- | :--- | :--- |
"""
    
    for item in history:
        tag = item.get("tag_name", "N/A")
        # 使用 UTC+8 格式化时间
        date_str = format_time_v8(item.get("published_at", ""))
        url = item.get("html_url", "#")
        
        # 简单列出资产
        assets_text = ""
        if "assets" in item:
            for asset in item["assets"]:
                # 使用 release 直接下载链接（如果已在 GitHub Release 中托管）
                # 这里假设我们会上传到当前的 Release，所以链接应该指向当前 Repo 的 Release
                # 但为了简单，我们先列出文件名
                assets_text += f"`{asset['name']}`<br>"
        
        md += f"| `{tag}` | {date_str} | {assets_text} | [Source]({url}) |\n"

    md += "\n---\n*Auto-generated by Antigravity Monitoring System*\n"
    return md

def 获取指定版本(tag):
    """通过 Tag 获取特定 Release"""
    url = f"{GITHUB_API_URL}/tags/{tag}"
    try:
        r = requests.get(url, headers=get_headers(), timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"获取版本 {tag} 失败: {e}")
        return None

def main():
    # 命令行模式
    if len(sys.argv) > 1:
        if sys.argv[1] == "--api-history":
            # 返回精简版本列表供 Matrix 使用 (避免 JSON 过大)
            releases = 获取所有版本()
            
            # 按照发布时间升序排列 (从小到大 / 旧到新)
            # 这样备份工作流会按照历史顺序依次创建 Release
            releases.sort(key=lambda x: x.get("published_at", ""))
            
            output = []
            for r in releases:
                output.append({
                    "version": r["tag_name"]
                })
            print(json.dumps(output))
            return

        if sys.argv[1] == "--download":
            # 下载指定版本的资源
            version_tag = sys.argv[2]
            print(f"正在处理版本 {version_tag} ...")
            
            # 使用 Tag直接获取，减少 API 调用
            target_release = 获取指定版本(version_tag)
            
            if target_release:
                # 下载资源
                file_list = 下载资源(target_release["assets"])
                
                # 写入 step output 供后续步骤使用
                if "GITHUB_OUTPUT" in os.environ:
                    with open(os.environ["GITHUB_OUTPUT"], "a", encoding='utf-8') as f:
                        # 格式化时间
                        pub_at = format_time_v8(target_release['published_at'])
                        
                        f.write(f"published_at={pub_at}\n")
                        f.write(f"html_url={target_release['html_url']}\n")
                        
                        # 清洗并写入 Body
                        body_content = normalize_text(target_release.get('body', 'No description'))
                        
                        # 使用 EOF 分隔符处理多行 body，避免 URL 编码问题
                        delimiter = f"EOF_{os.urandom(6).hex()}"
                        f.write(f"body<<{delimiter}\n")
                        f.write(body_content)
                        f.write(f"\n{delimiter}\n")
                        
                        # 使用 EOF 分隔符输出多行内容，确保 gh-release 能正确识别文件列表
                        f.write("assets<<EOF\n")
                        f.write('\n'.join(file_list))
                        f.write("\nEOF\n")
            else:
                print(f"未找到版本 {version_tag}")
                sys.exit(1)
            return

    # 默认模式：检查更新 (Hourly Job)
    print("开始检查最新版本...")
    latest_release = 获取最新版本()
    if not latest_release:
        print("无法获取最新版本")
        sys.exit(1)

    tag_name = latest_release["tag_name"]
    published_at_raw = latest_release["published_at"]
    
    # 读取本地版本
    local_version = ""
    if os.path.exists("VERSION"):
        with open("VERSION", "r", encoding="utf-8") as f:
            local_version = f.read().strip()
            
    print(f"本地版本: {local_version}, 远程最新: {tag_name}")
    
    # 只有当版本不同时才触发动作
    version_changed = (tag_name != local_version)
    
    # 更新历史记录 (无论是否变化，都确保历史记录是最新的)
    history = 加载历史记录()
    # 检查是否已存在
    exists = any(item["tag_name"] == tag_name for item in history)
    if not exists:
        history.insert(0, {
            "tag_name": tag_name,
            "published_at": published_at_raw,
            "html_url": latest_release["html_url"],
            "assets": [{"name": a["name"], "browser_download_url": a["browser_download_url"]} for a in latest_release["assets"]]
        })
        保存历史记录(history)
    
    readme_content = 生成README(history)
    with open("README.md", "w", encoding="utf-8") as f:
        f.write(readme_content)
        
    # 写入 Output
    if "GITHUB_OUTPUT" in os.environ:
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding='utf-8') as f:
            f.write(f"version_changed={'true' if version_changed else 'false'}\n")
            f.write(f"version={tag_name}\n")
            
            # 清洗并写入 Body
            body_content = normalize_text(latest_release.get('body', 'No description'))
            
            # 使用 EOF 分隔符处理 Body
            delimiter = f"EOF_{os.urandom(6).hex()}"
            f.write(f"body<<{delimiter}\n")
            f.write(body_content)
            f.write(f"\n{delimiter}\n")
            
            if version_changed:
                print("版本更新，开始下载资源...")
                file_list = 下载资源(latest_release["assets"])
                
                f.write("assets<<EOF\n")
                f.write('\n'.join(file_list))
                f.write("\nEOF\n")
                
                # 更新本地 VERSION 文件
                with open("VERSION", "w", encoding="utf-8") as vf:
                    vf.write(tag_name)

if __name__ == "__main__":
    main()
