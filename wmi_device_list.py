#!/usr/bin/env python3
"""
WMI Device List - WMIで取得できるデバイス一覧表示スクリプト
"""

import json
from collections import defaultdict

try:
    import wmi
    HAS_WMI = True
except ImportError:
    HAS_WMI = False

def list_all_wmi_devices():
    """WMIで取得可能なすべてのデバイスを表示"""
    if not HAS_WMI:
        print("Error: WMI module not available. Install with: pip install WMI")
        return
    
    print("=" * 80)
    print(" WMI Device List - All Available Devices")
    print("=" * 80)
    
    try:
        c = wmi.WMI()
        
        # PnP デバイス一覧
        print("\n1. Plug and Play Devices (Win32_PnPEntity)")
        print("-" * 50)
        
        devices = c.Win32_PnPEntity()
        device_categories = defaultdict(list)
        
        for i, device in enumerate(devices):
            device_name = str(getattr(device, 'Name', 'Unknown'))
            device_desc = str(getattr(device, 'Description', 'Unknown'))
            device_id = str(getattr(device, 'DeviceID', 'Unknown'))
            device_class = str(getattr(device, 'PNPClass', 'Unknown'))
            status = str(getattr(device, 'Status', 'Unknown'))
            
            device_info = {
                'name': device_name,
                'description': device_desc,
                'device_id': device_id,
                'class': device_class,
                'status': status
            }
            
            device_categories[device_class].append(device_info)
        
        # カテゴリ別に表示
        for category, devices_in_category in sorted(device_categories.items()):
            if category != 'Unknown' and len(devices_in_category) > 0:
                print(f"\n  Category: {category} ({len(devices_in_category)} devices)")
                for device in devices_in_category[:5]:  # 各カテゴリの最初の5個を表示
                    print(f"    • {device['name']}")
                    if device['description'] != device['name']:
                        print(f"      Description: {device['description']}")
                    print(f"      Status: {device['status']}")
                
                if len(devices_in_category) > 5:
                    print(f"    ... and {len(devices_in_category) - 5} more devices")
        
        print(f"\nTotal PnP devices found: {len(devices)}")
        
    except Exception as e:
        print(f"Error accessing WMI PnP devices: {e}")

def list_processors():
    """プロセッサー情報を詳細表示"""
    if not HAS_WMI:
        return
    
    print("\n" + "=" * 80)
    print(" Processor Information (Win32_Processor)")
    print("=" * 80)
    
    try:
        c = wmi.WMI()
        processors = c.Win32_Processor()
        
        for i, processor in enumerate(processors, 1):
            print(f"\nProcessor {i}:")
            print(f"  Name: {getattr(processor, 'Name', 'Unknown')}")
            print(f"  Manufacturer: {getattr(processor, 'Manufacturer', 'Unknown')}")
            print(f"  Description: {getattr(processor, 'Description', 'Unknown')}")
            print(f"  Architecture: {getattr(processor, 'Architecture', 'Unknown')}")
            print(f"  Family: {getattr(processor, 'Family', 'Unknown')}")
            print(f"  Model: {getattr(processor, 'Model', 'Unknown')}")
            print(f"  NumberOfCores: {getattr(processor, 'NumberOfCores', 'Unknown')}")
            print(f"  NumberOfLogicalProcessors: {getattr(processor, 'NumberOfLogicalProcessors', 'Unknown')}")
            print(f"  MaxClockSpeed: {getattr(processor, 'MaxClockSpeed', 'Unknown')} MHz")
            print(f"  ProcessorId: {getattr(processor, 'ProcessorId', 'Unknown')}")
            
    except Exception as e:
        print(f"Error accessing processor information: {e}")

def list_system_devices():
    """システムデバイス情報を表示"""
    if not HAS_WMI:
        return
    
    print("\n" + "=" * 80)
    print(" System Devices (Win32_SystemDevice)")
    print("=" * 80)
    
    try:
        c = wmi.WMI()
        devices = c.Win32_SystemDevice()
        
        device_types = defaultdict(list)
        
        for device in devices:
            device_name = str(getattr(device, 'Name', 'Unknown'))
            device_desc = str(getattr(device, 'Description', 'Unknown'))
            pnp_device_id = str(getattr(device, 'PNPDeviceID', 'Unknown'))
            
            # デバイスタイプを推定
            device_type = "Other"
            if "ai" in device_name.lower() or "npu" in device_name.lower():
                device_type = "AI/NPU"
            elif "audio" in device_name.lower() or "sound" in device_name.lower():
                device_type = "Audio"
            elif "video" in device_name.lower() or "display" in device_name.lower():
                device_type = "Display"
            elif "network" in device_name.lower() or "ethernet" in device_name.lower():
                device_type = "Network"
            elif "usb" in device_name.lower():
                device_type = "USB"
            elif "storage" in device_name.lower() or "disk" in device_name.lower():
                device_type = "Storage"
            
            device_types[device_type].append({
                'name': device_name,
                'description': device_desc,
                'pnp_id': pnp_device_id
            })
        
        for device_type, devices_list in sorted(device_types.items()):
            if len(devices_list) > 0:
                print(f"\n  {device_type} Devices ({len(devices_list)} found):")
                for device in devices_list[:10]:  # 最初の10個を表示
                    print(f"    • {device['name']}")
                    if device['description'] != device['name']:
                        print(f"      Description: {device['description']}")
                
                if len(devices_list) > 10:
                    print(f"    ... and {len(devices_list) - 10} more devices")
    
    except Exception as e:
        print(f"Error accessing system devices: {e}")

def search_ai_npu_devices():
    """AI/NPU関連デバイスを詳細検索"""
    if not HAS_WMI:
        return
    
    print("\n" + "=" * 80)
    print(" AI/NPU Device Search")
    print("=" * 80)
    
    ai_keywords = [
        'ai boost', 'npu', 'neural', 'ai accelerator', 'inference',
        'machine learning', 'deep learning', 'qualcomm', 'snapdragon',
        'intel ai', 'amd ai', 'neural processor', 'ai engine',
        'directml', 'windows ml', 'onnx'
    ]
    
    try:
        c = wmi.WMI()
        
        # 複数のWMIクラスから検索
        wmi_classes = [
            ('Win32_PnPEntity', 'Plug and Play Devices'),
            ('Win32_SystemDevice', 'System Devices'),
            ('Win32_Processor', 'Processors'),
            ('Win32_VideoController', 'Video Controllers')
        ]
        
        found_devices = []
        
        for wmi_class, class_desc in wmi_classes:
            print(f"\nSearching in {class_desc} ({wmi_class})...")
            
            try:
                devices = getattr(c, wmi_class)()
                class_matches = []
                
                for device in devices:
                    device_name = str(getattr(device, 'Name', '')).lower()
                    device_desc = str(getattr(device, 'Description', '')).lower()
                    device_id = str(getattr(device, 'DeviceID', ''))
                    
                    matched_keywords = []
                    for keyword in ai_keywords:
                        if keyword in device_name or keyword in device_desc:
                            matched_keywords.append(keyword)
                    
                    if matched_keywords:
                        device_info = {
                            'class': wmi_class,
                            'name': str(getattr(device, 'Name', '')),
                            'description': str(getattr(device, 'Description', '')),
                            'device_id': device_id,
                            'matched_keywords': matched_keywords
                        }
                        
                        # 追加の属性取得
                        if wmi_class == 'Win32_Processor':
                            device_info['manufacturer'] = str(getattr(device, 'Manufacturer', ''))
                            device_info['family'] = str(getattr(device, 'Family', ''))
                        
                        class_matches.append(device_info)
                        found_devices.append(device_info)
                
                if class_matches:
                    print(f"  Found {len(class_matches)} AI/NPU related devices:")
                    for device in class_matches:
                        print(f"    ✓ {device['name']}")
                        print(f"      Description: {device['description']}")
                        print(f"      Matched keywords: {', '.join(device['matched_keywords'])}")
                        if 'manufacturer' in device:
                            print(f"      Manufacturer: {device['manufacturer']}")
                        print(f"      Device ID: {device['device_id'][:50]}..." if len(device['device_id']) > 50 else f"      Device ID: {device['device_id']}")
                        print()
                else:
                    print("  No AI/NPU related devices found")
                    
            except Exception as e:
                print(f"  Error searching {wmi_class}: {e}")
        
        print(f"\nTotal AI/NPU related devices found: {len(found_devices)}")
        
        if found_devices:
            print("\n" + "=" * 40)
            print(" Summary of AI/NPU Devices")
            print("=" * 40)
            for i, device in enumerate(found_devices, 1):
                print(f"{i}. {device['name']} ({device['class']})")
                print(f"   Keywords: {', '.join(device['matched_keywords'])}")
        
    except Exception as e:
        print(f"Error in AI/NPU device search: {e}")

def export_device_list_to_json():
    """デバイス一覧をJSONファイルにエクスポート"""
    if not HAS_WMI:
        return
    
    print("\n" + "=" * 80)
    print(" Exporting Device List to JSON")
    print("=" * 80)
    
    try:
        c = wmi.WMI()
        
        export_data = {
            'timestamp': str(__import__('datetime').datetime.now()),
            'pnp_devices': [],
            'processors': [],
            'system_devices': []
        }
        
        # PnP デバイス
        print("Collecting PnP devices...")
        devices = c.Win32_PnPEntity()
        for device in devices:
            device_data = {
                'name': str(getattr(device, 'Name', '')),
                'description': str(getattr(device, 'Description', '')),
                'device_id': str(getattr(device, 'DeviceID', '')),
                'class': str(getattr(device, 'PNPClass', '')),
                'status': str(getattr(device, 'Status', ''))
            }
            export_data['pnp_devices'].append(device_data)
        
        # プロセッサー
        print("Collecting processor information...")
        processors = c.Win32_Processor()
        for processor in processors:
            processor_data = {
                'name': str(getattr(processor, 'Name', '')),
                'manufacturer': str(getattr(processor, 'Manufacturer', '')),
                'description': str(getattr(processor, 'Description', '')),
                'architecture': str(getattr(processor, 'Architecture', '')),
                'family': str(getattr(processor, 'Family', '')),
                'model': str(getattr(processor, 'Model', '')),
                'cores': str(getattr(processor, 'NumberOfCores', '')),
                'logical_processors': str(getattr(processor, 'NumberOfLogicalProcessors', '')),
                'max_clock_speed': str(getattr(processor, 'MaxClockSpeed', ''))
            }
            export_data['processors'].append(processor_data)
        
        # システムデバイス
        print("Collecting system devices...")
        sys_devices = c.Win32_SystemDevice()
        for device in sys_devices:
            device_data = {
                'name': str(getattr(device, 'Name', '')),
                'description': str(getattr(device, 'Description', '')),
                'pnp_device_id': str(getattr(device, 'PNPDeviceID', ''))
            }
            export_data['system_devices'].append(device_data)
        
        # JSONファイルに保存
        filename = 'wmi_device_list.json'
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        print(f"Device list exported to: {filename}")
        print(f"  PnP Devices: {len(export_data['pnp_devices'])}")
        print(f"  Processors: {len(export_data['processors'])}")
        print(f"  System Devices: {len(export_data['system_devices'])}")
        
    except Exception as e:
        print(f"Error exporting device list: {e}")

def main():
    """メイン関数"""
    print("WMI Device List Utility")
    print("Comprehensive WMI device information display")
    print()
    
    if not HAS_WMI:
        print("ERROR: WMI module not installed")
        print("Please install with: pip install WMI")
        return
    
    # すべてのデバイスリスト表示
    list_all_wmi_devices()
    
    # プロセッサー詳細情報
    list_processors()
    
    # システムデバイス
    list_system_devices()
    
    # AI/NPU デバイス検索
    search_ai_npu_devices()
    
    # JSON エクスポート
    export_device_list_to_json()
    
    print("\n" + "=" * 80)
    print(" WMI Device List Complete")
    print("=" * 80)

if __name__ == "__main__":
    main()