"""
临时修复脚本：为已存在的世界生成缺失的 locations.json 和 time.json
"""
import os
import sys
import json

# 添加项目路径
sys.path.insert(0, os.path.dirname(__file__))

from app.services.components.asset_generator import AssetGenerator
from app.core.config import settings

def fix_world_assets(world_id: str):
    """为指定世界生成缺失的资源文件"""
    print(f"正在修复世界 {world_id} 的资源文件...")
    
    # 读取 bible.json
    world_dir = os.path.join(settings.DATA_DIR, "worlds", world_id)
    bible_path = os.path.join(world_dir, "bible.json")
    
    if not os.path.exists(bible_path):
        print(f"❌ 错误：找不到 {bible_path}")
        return False
    
    with open(bible_path, "r", encoding="utf-8") as f:
        bible_data = json.load(f)
    
    print(f"✅ 成功加载 bible.json")
    print(f"   - 场景名称: {bible_data.get('scene', {}).get('name', 'N/A')}")
    print(f"   - 地点数量: {len(bible_data.get('scene', {}).get('locations', []))}")
    print(f"   - 时间配置: {bible_data.get('time_config', {}).get('display_year', 'N/A')}")
    
    # 使用修复后的 AssetGenerator
    generator = AssetGenerator()
    generator.extract_assets_from_bible(world_id, bible_data)
    
    # 验证文件是否生成
    locations_path = os.path.join(world_dir, "locations.json")
    time_path = os.path.join(world_dir, "time.json")
    
    success = True
    if os.path.exists(locations_path):
        with open(locations_path, "r", encoding="utf-8") as f:
            locs = json.load(f)
        print(f"✅ locations.json 已生成 ({len(locs.get('locations', []))} 个地点)")
    else:
        print(f"❌ locations.json 生成失败")
        success = False
    
    if os.path.exists(time_path):
        with open(time_path, "r", encoding="utf-8") as f:
            time_cfg = json.load(f)
        print(f"✅ time.json 已生成 ({time_cfg.get('display_year', 'N/A')})")
    else:
        print(f"❌ time.json 生成失败")
        success = False
    
    return success

if __name__ == "__main__":
    # 你的世界 ID
    WORLD_ID = "952d8435-aa2a-45b9-a692-504dadcade43"
    
    print("=" * 60)
    print("🔧 theNPC 资源修复工具")
    print("=" * 60)
    
    if fix_world_assets(WORLD_ID):
        print("\n🎉 修复完成！locations.json 和 time.json 已生成")
    else:
        print("\n⚠️ 修复过程中出现错误，请检查日志")
    
    print("=" * 60)
