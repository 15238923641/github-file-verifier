#!/usr/bin/env python3
# =============================================================================
# GitHub Asset Verification Script
# 功能：验证GitHub仓库中的文件存在性、结构、内容和提交记录
# 依赖: requests, python-dotenv (安装命令: pip install requests python-dotenv)
# =============================================================================

import sys
import os
import requests
import base64
import re
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv

# --------------------------
# 配置部分（可根据需要修改）
# --------------------------
VERIFICATION_CONFIG = {
    # 目标仓库信息
    "target_repo": "claude-code",
    
    # 目标文件信息
    "target_file": {
        "path": "CLAUDE_COLLABORATION_ANALYSIS.md",
        "branch": "main"
    },
    
    # 必需结构（文件必须包含的内容）
    "required_structures": [
        "# Claude AI 协作分析",
        "## 汇总统计",
        "| Developer | GitHub Username |"
    ],
    
    # 内容验证规则
    "content_rules": [
        # 规则1：统计数据匹配
        {
            "type": "stat_match",
            "target": "分析的提交总数：",
            "expected": "158"
        },
        # 规则2：正则匹配
        {
            "type": "regex_match",
            "target": "共同创作者邮箱",
            "expected": r"noreply@anthropic\.com"
        },
        # 规则3：固定文本匹配
        {
            "type": "text_match",
            "target": "验证状态",
            "expected": "验证状态：通过"
        }
    ],
    
    # 提交记录验证（可选）
    "commit_verification": {
        "msg_pattern": "添加 Claude AI 协作分析报告",
        "max_commits": 10
    }
}

# --------------------------
# 工具函数
# --------------------------
def load_env() -> Tuple[Optional[str], Optional[str]]:
    """加载环境变量"""
    load_dotenv(".env")
    github_token = os.environ.get("GITHUB_TOKEN")
    github_org = os.environ.get("GITHUB_ORG")
    return github_token, github_org


def build_headers(github_token: str) -> Dict[str, str]:
    """构建GitHub API请求头"""
    return {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }


def call_github_api(
    endpoint: str,
    headers: Dict[str, str],
    org: str,
    repo: str
) -> Tuple[bool, Optional[Dict]]:
    """调用GitHub API"""
    url = f"https://api.github.com/repos/{org}/{repo}/{endpoint}"
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return True, response.json()
        elif response.status_code == 404:
            print(f"[API 提示] {endpoint} 资源未找到（404）", file=sys.stderr)
            return False, None
        else:
            print(f"[API 错误] {endpoint} 状态码：{response.status_code}", file=sys.stderr)
            return False, None
    except Exception as e:
        print(f"[API 异常] 调用 {endpoint} 失败：{str(e)}", file=sys.stderr)
        return False, None


def get_repo_file_content(
    file_path: str,
    headers: Dict[str, str],
    org: str,
    repo: str,
    branch: str = "main"
) -> Optional[str]:
    """获取文件内容"""
    success, result = call_github_api(
        f"contents/{file_path}?ref={branch}", headers, org, repo
    )
    if not success or not result:
        return None

    try:
        return base64.b64decode(result.get("content", "")).decode("utf-8")
    except Exception as e:
        print(f"[文件解码错误] {file_path}：{str(e)}", file=sys.stderr)
        return None


def search_commits(
    headers: Dict[str, str],
    org: str,
    repo: str,
    commit_msg_pattern: str,
    max_commits: int = 10
) -> bool:
    """搜索提交记录"""
    success, commits = call_github_api(
        f"commits?per_page={max_commits}", headers, org, repo
    )
    if not success:
        return False

    pattern = re.compile(commit_msg_pattern, re.IGNORECASE)
    for commit in commits:
        if pattern.search(commit["commit"]["message"]):
            return True
    return False


# --------------------------
# 验证逻辑
# --------------------------
def verify_file_existence(
    config: Dict,
    headers: Dict[str, str],
    org: str,
    repo: str
) -> Tuple[bool, Optional[str]]:
    """验证文件存在性"""
    file_path = config["target_file"]["path"]
    branch = config["target_file"]["branch"]
    print(f"[1/4] 验证文件存在性：{file_path}（分支：{branch}）...")
    
    content = get_repo_file_content(file_path, headers, org, repo, branch)
    if not content:
        print(f"[错误] 文件 {file_path} 在 {branch} 分支中未找到", file=sys.stderr)
        return False, None
    print(f"[成功] 文件 {file_path} 存在")
    return True, content


def verify_file_structure(
    content: str,
    config: Dict
) -> bool:
    """验证文件结构"""
    required_structures = config["required_structures"]
    print(f"[2/4] 验证文件结构：共需包含 {len(required_structures)} 个必需结构...")
    
    missing = []
    for struct in required_structures:
        if struct not in content:
            missing.append(struct)
    
    if missing:
        print(f"[错误] 缺失必需结构：{', '.join(missing)}", file=sys.stderr)
        return False
    print(f"[成功] 所有必需结构均存在")
    return True


def verify_content_accuracy(
    content: str,
    config: Dict
) -> bool:
    """验证内容准确性"""
    content_rules = config["content_rules"]
    if not content_rules:
        print(f"[3/4 跳过] 未配置内容验证规则，直接通过")
        return True
    
    print(f"[3/4] 验证内容准确性：共需校验 {len(content_rules)} 条规则...")
    lines = content.split("\n")
    
    for rule in content_rules:
        rule_type = rule["type"]
        target = rule["target"]
        expected = rule["expected"]
        matched = False
        
        if rule_type == "stat_match":
            for line in lines:
                if target in line:
                    match = re.search(r"(\d+)", line)
                    if match and match.group(1) == str(expected):
                        matched = True
                        break
        
        elif rule_type == "regex_match":
            if re.search(expected, content):
                matched = True
        
        elif rule_type == "text_match":
            if expected in content:
                matched = True
        
        if not matched:
            print(f"[错误] 内容规则校验失败：{target} 预期 {expected}，实际未匹配", file=sys.stderr)
            return False
    
    print(f"[成功] 所有内容规则校验通过")
    return True


def verify_commit_record(
    config: Dict,
    headers: Dict[str, str],
    org: str,
    repo: str
) -> bool:
    """验证提交记录"""
    commit_config = config.get("commit_verification")
    if not commit_config:
        print(f"[4/4 跳过] 未配置提交验证规则，直接通过")
        return True
    
    commit_msg_pattern = commit_config["msg_pattern"]
    max_commits = commit_config.get("max_commits", 10)
    print(f"[4/4] 验证提交记录：搜索包含「{commit_msg_pattern}」的最近 {max_commits} 条提交...")
    
    found = search_commits(headers, org, repo, commit_msg_pattern, max_commits)
    if not found:
        print(f"[错误] 未找到符合要求的提交记录", file=sys.stderr)
        return False
    print(f"[成功] 找到符合要求的提交记录")
    return True


# --------------------------
# 主流程
# --------------------------
def run_verification(config: Dict) -> bool:
    """执行完整验证流程"""
    print("=" * 50)
    print("开始执行GitHub资产验证")
    print("=" * 50)
    
    # 加载环境变量
    github_token, github_org = load_env()
    if not github_token:
        print("[环境错误] 未配置GITHUB_TOKEN（需在.env中设置）", file=sys.stderr)
        return False
    if not github_org:
        print("[环境错误] 未配置GITHUB_ORG（需在.env中设置）", file=sys.stderr)
        return False
    
    repo_name = config["target_repo"]
    headers = build_headers(github_token)
    print(f"[环境就绪] 目标仓库：{github_org}/{repo_name}\n")

    # 执行验证步骤
    file_exists, file_content = verify_file_existence(config, headers, github_org, repo_name)
    if not file_exists:
        return False

    structure_valid = verify_file_structure(file_content, config)
    if not structure_valid:
        return False

    content_valid = verify_content_accuracy(file_content, config)
    if not content_valid:
        return False

    commit_valid = verify_commit_record(config, headers, github_org, repo_name)
    if not commit_valid:
        return False

    # 验证通过
    print("\n" + "=" * 50)
    print("✅ 所有验证步骤通过！")
    print(f"验证对象：{config['target_file']['path']}")
    print(f"目标仓库：{github_org}/{repo_name}")
    print("=" * 50)
    return True


if __name__ == "__main__":
    # 执行验证
    success = run_verification(VERIFICATION_CONFIG)
    sys.exit(0 if success else 1)