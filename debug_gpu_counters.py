#!/usr/bin/env python3
"""
GPU Performance Counters デバッグスクリプト
"""
import win32pdh

def list_all_gpu_counters():
    """利用可能なすべてのGPU関連カウンターを表示"""
    print("=== Available GPU Performance Counters ===")
    
    # GPU Engine関連のカウンターを確認
    try:
        gpu_paths = win32pdh.ExpandCounterPath(r"\GPU Engine(*)\*")
        print(f"\nFound {len(gpu_paths)} GPU Engine counters:")
        for i, path in enumerate(gpu_paths[:20]):  # 最初の20個のみ表示
            print(f"  {i+1:2d}: {path}")
        if len(gpu_paths) > 20:
            print(f"  ... and {len(gpu_paths) - 20} more")
    except Exception as e:
        print(f"Error getting GPU Engine counters: {e}")
    
    # GPU Process Memory関連のカウンターを確認
    try:
        gpu_mem_paths = win32pdh.ExpandCounterPath(r"\GPU Process Memory(*)\*")
        print(f"\nFound {len(gpu_mem_paths)} GPU Process Memory counters:")
        for i, path in enumerate(gpu_mem_paths[:10]):  # 最初の10個のみ表示
            print(f"  {i+1:2d}: {path}")
        if len(gpu_mem_paths) > 10:
            print(f"  ... and {len(gpu_mem_paths) - 10} more")
    except Exception as e:
        print(f"Error getting GPU Process Memory counters: {e}")
    
    # GPU Adapter Memory関連のカウンターを確認
    try:
        gpu_adapter_paths = win32pdh.ExpandCounterPath(r"\GPU Adapter Memory(*)\*")
        print(f"\nFound {len(gpu_adapter_paths)} GPU Adapter Memory counters:")
        for i, path in enumerate(gpu_adapter_paths[:10]):  # 最初の10個のみ表示
            print(f"  {i+1:2d}: {path}")
        if len(gpu_adapter_paths) > 10:
            print(f"  ... and {len(gpu_adapter_paths) - 10} more")
    except Exception as e:
        print(f"Error getting GPU Adapter Memory counters: {e}")

def check_specific_compute_patterns():
    """特定のCompute関連パターンをチェック"""
    print("\n=== Checking specific Compute patterns ===")
    
    patterns = [
        r"\GPU Engine(*)\Utilization Percentage",
        r"\GPU Engine(*)/*Compute*",
        r"\GPU Engine(*)\*",
        r"\GPU Engine(engtype_Compute)\Utilization Percentage",
        r"\GPU Engine(*engtype_Compute*)\Utilization Percentage",
        r"\GPU Engine(*Compute*)\Utilization Percentage",
    ]
    
    for pattern in patterns:
        try:
            paths = win32pdh.ExpandCounterPath(pattern)
            print(f"\nPattern: {pattern}")
            print(f"Found {len(paths)} counters:")
            
            # Compute関連のもののみ表示
            compute_paths = [p for p in paths if 'compute' in p.lower()]
            for path in compute_paths[:10]:
                print(f"  {path}")
            if len(compute_paths) > 10:
                print(f"  ... and {len(compute_paths) - 10} more compute counters")
                
        except Exception as e:
            print(f"Pattern {pattern} failed: {e}")

def test_compute_counter_access():
    """Computeカウンターへの実際のアクセステスト"""
    print("\n=== Testing Compute Counter Access ===")
    
    try:
        # すべてのGPU Engineカウンターを取得
        all_paths = win32pdh.ExpandCounterPath(r"\GPU Engine(*)\Utilization Percentage")
        compute_paths = [p for p in all_paths if 'compute' in p.lower()]
        
        if not compute_paths:
            print("No Compute counters found!")
            return
        
        print(f"Found {len(compute_paths)} Compute counters:")
        for path in compute_paths[:5]:
            print(f"  {path}")
        
        # 実際にクエリを作成してテスト
        query = win32pdh.OpenQuery()
        counters = []
        
        for path in compute_paths[:3]:  # 最初の3つをテスト
            try:
                handle = win32pdh.AddCounter(query, path)
                counters.append((handle, path))
                print(f"✓ Successfully added: {path}")
            except Exception as e:
                print(f"✗ Failed to add {path}: {e}")
        
        if counters:
            # データ収集テスト
            try:
                win32pdh.CollectQueryData(query)
                print("\n=== Counter Values ===")
                
                import time
                time.sleep(1)  # 1秒待機
                win32pdh.CollectQueryData(query)
                
                for handle, path in counters:
                    try:
                        t, val = win32pdh.GetFormattedCounterValue(handle, win32pdh.PDH_FMT_DOUBLE)
                        instance = path[path.find('(')+1:path.find(')')] if '(' in path and ')' in path else path
                        print(f"  {instance}: {val:.1f}%")
                    except Exception as e:
                        print(f"  {path}: Error reading value - {e}")
                        
            except Exception as e:
                print(f"Error collecting data: {e}")
        
        win32pdh.CloseQuery(query)
        
    except Exception as e:
        print(f"Error in compute counter test: {e}")

if __name__ == "__main__":
    list_all_gpu_counters()
    check_specific_compute_patterns()
    test_compute_counter_access()