# NPU の代替監視方法を試すスクリプト
import time

def check_wmi_npu():
    """WMI を使用してNPU情報を取得"""
    try:
        import wmi
        c = wmi.WMI()
        
        print("=== WMI でのNPU/AI関連デバイス検索 ===")
        
        # さまざまなWMIクラスでNPU関連デバイスを検索
        search_classes = [
            'Win32_PnPEntity',
            'Win32_SystemDevice', 
            'Win32_Processor',
            'Win32_VideoController'
        ]
        
        npu_keywords = [
            'npu', 'neural', 'ai', 'accelerator', 'inference',
            'qualcomm', 'snapdragon', 'intel', 'amd'
        ]
        
        found_devices = []
        
        for class_name in search_classes:
            try:
                print(f"\n{class_name} を検索中...")
                devices = getattr(c, class_name)()
                
                for device in devices:
                    device_name = str(getattr(device, 'Name', ''))
                    device_desc = str(getattr(device, 'Description', ''))
                    
                    # NPU関連キーワードを含むデバイスを検索
                    for keyword in npu_keywords:
                        if keyword.lower() in device_name.lower() or keyword.lower() in device_desc.lower():
                            found_devices.append({
                                'class': class_name,
                                'name': device_name,
                                'description': device_desc
                            })
                            print(f"  見つかりました: {device_name}")
                            break
                            
            except Exception as e:
                print(f"  {class_name} でエラー: {e}")
        
        if found_devices:
            print(f"\n=== 見つかったNPU関連デバイス: {len(found_devices)}個 ===")
            for i, device in enumerate(found_devices, 1):
                print(f"{i}. クラス: {device['class']}")
                print(f"   名前: {device['name']}")
                print(f"   説明: {device['description']}")
                print()
        else:
            print("\nNPU関連デバイスは見つかりませんでした")
            
    except ImportError:
        print("WMI ライブラリがインストールされていません")
        print("pip install WMI でインストールしてください")
    except Exception as e:
        print(f"WMI エラー: {e}")

def check_device_manager():
    """デバイスマネージャー情報を取得"""
    print("\n=== デバイスマネージャー情報 ===")
    
    try:
        import subprocess
        
        # デバイス一覧を取得
        result = subprocess.run([
            'powershell', '-Command',
            'Get-WmiObject -Class Win32_PnPEntity | Where-Object {$_.Name -match "NPU|Neural|AI|Accelerator|Qualcomm|Snapdragon"} | Select-Object Name, Description, DeviceID'
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0 and result.stdout.strip():
            print("NPU関連デバイス:")
            print(result.stdout)
        else:
            print("NPU関連デバイスが見つかりませんでした")
            
    except Exception as e:
        print(f"デバイス情報取得エラー: {e}")

def check_task_manager_equivalent():
    """タスクマネージャー相当の情報を確認"""
    print("\n=== プロセッサー情報 ===")
    
    try:
        import subprocess
        
        # プロセッサー情報
        result = subprocess.run([
            'wmic', 'cpu', 'get', 'name,description,manufacturer'
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("CPU情報:")
            print(result.stdout)
        
        # システム情報でNPU関連を検索
        result = subprocess.run([
            'systeminfo'
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            lines = result.stdout.split('\n')
            npu_related = []
            for line in lines:
                if any(keyword in line.lower() for keyword in ['npu', 'neural', 'ai', 'accelerator']):
                    npu_related.append(line.strip())
            
            if npu_related:
                print("\nシステム情報内のNPU関連:")
                for line in npu_related:
                    print(f"  {line}")
            else:
                print("\nシステム情報にNPU関連項目なし")
                
    except Exception as e:
        print(f"システム情報エラー: {e}")

def suggest_alternatives():
    """代替監視方法の提案"""
    print("\n=== NPU監視の代替案 ===")
    print("1. ハードウェア確認:")
    print("   - タスクマネージャー > パフォーマンス タブでNPUが表示されるか確認")
    print("   - デバイスマネージャーで「システムデバイス」内にNPU関連デバイスがあるか確認")
    print("")
    print("2. ソフトウェア確認:")
    print("   - Windows AIプラットフォーム (Windows ML) がインストールされているか")
    print("   - NPU対応アプリケーション（例：Windows Studio Effects）が動作するか")
    print("")
    print("3. 代替監視方法:")
    print("   - プロセス別CPU使用率の監視")
    print("   - AI関連プロセス（例：RuntimeBroker、dwm.exe）の監視")
    print("   - 電力消費パターンの監視")
    print("")
    print("4. 将来の対応:")
    print("   - Windows 11 24H2以降へのアップデート")
    print("   - NPU対応デバイスドライバーの最新版インストール")
    print("   - ONNX Runtime、DirectML等のAIフレームワーク使用時の間接的監視")

if __name__ == "__main__":
    check_wmi_npu()
    check_device_manager()
    check_task_manager_equivalent()
    suggest_alternatives()