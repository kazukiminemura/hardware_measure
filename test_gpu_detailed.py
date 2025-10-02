#!/usr/bin/env python3
"""
GPU詳細情報テストスクリプト
"""

import json
from hardware_measure import HardwareMonitor

def test_gpu_detailed_info():
    """GPU詳細情報をテスト"""
    print("=== GPU Detailed Information Test ===")
    print()
    
    # HardwareMonitorインスタンスを作成
    monitor = HardwareMonitor()
    
    # GPU詳細情報を取得
    gpu_info = monitor.get_gpu_detailed_info()
    
    print("GPU詳細情報:")
    print("-" * 50)
    print(f"利用可能: {gpu_info['available']}")
    print(f"Compute使用率: {gpu_info['compute_percent']:.1f}%")
    print(f"全体使用率: {gpu_info['overall_percent']:.1f}%")
    print(f"監視方法: {gpu_info['method']}")
    print()
    
    if gpu_info['engines']:
        print("検出されたGPUエンジン:")
        for name, usage in gpu_info['engines'].items():
            print(f"  {name}: {usage:.1f}%")
        print()
    
    if gpu_info['compute_engines']:
        print("Computeエンジン (トップ3):")
        for name, usage in gpu_info['compute_engines']:
            print(f"  {name}: {usage:.1f}%")
        print()
    
    if gpu_info['top_engines']:
        print("全エンジン (トップ3):")
        for name, usage in gpu_info['top_engines']:
            print(f"  {name}: {usage:.1f}%")
        print()
    
    # JSON形式でも出力
    print("JSON形式:")
    print(json.dumps(gpu_info, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    test_gpu_detailed_info()