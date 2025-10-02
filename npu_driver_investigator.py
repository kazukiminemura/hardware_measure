#!/usr/bin/env python3
"""
NPU ドライバー・サービス状態調査スクリプト
Intel NPUの詳細な状態とドライバー情報を調査
"""

import subprocess
import sys
import os
from typing import Dict, List, Optional
import json

class NPUDriverInvestigator:
    """NPU ドライバー・サービス調査クラス"""
    
    def __init__(self):
        self.npu_related_services = []
        self.npu_devices = []
        self.driver_info = {}
    
    def check_administrator_privileges(self) -> bool:
        """管理者権限の確認"""
        try:
            # 管理者権限でのみアクセス可能なレジストリキーにアクセス試行
            result = subprocess.run(
                ["reg", "query", "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System", "/v", "EnableLUA"],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except:
            return False
    
    def discover_npu_services(self) -> List[Dict[str, str]]:
        """NPU関連サービスの発見"""
        print("Discovering NPU-related Windows services...")
        
        try:
            # Get-Service でサービス一覧を取得
            result = subprocess.run(
                ["powershell", "-Command", "Get-Service | ConvertTo-Json"],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                print(f"Error getting services: {result.stderr}")
                return []
            
            services = json.loads(result.stdout)
            npu_services = []
            
            npu_keywords = ['npu', 'neural', 'ai', 'intel', 'boost', 'accelerator']
            
            for service in services:
                service_name = service.get('Name', '').lower()
                display_name = service.get('DisplayName', '').lower()
                
                if any(keyword in service_name or keyword in display_name for keyword in npu_keywords):
                    npu_services.append({
                        'Name': service.get('Name', ''),
                        'DisplayName': service.get('DisplayName', ''),
                        'Status': service.get('Status', ''),
                        'StartType': service.get('StartType', '')
                    })
                    print(f"  Found: {service.get('DisplayName', service.get('Name', 'Unknown'))}")
                    print(f"    Status: {service.get('Status', 'Unknown')}")
            
            return npu_services
            
        except Exception as e:
            print(f"Error discovering NPU services: {e}")
            return []
    
    def check_npu_device_status(self) -> List[Dict[str, str]]:
        """NPUデバイス状態の確認"""
        print("\\nChecking NPU device status via Device Manager...")
        
        try:
            # デバイスマネージャー情報を取得
            result = subprocess.run([
                "powershell", "-Command",
                "Get-WmiObject -Class Win32_PnPEntity | Where-Object {$_.Name -like '*NPU*' -or $_.Name -like '*Neural*' -or $_.Name -like '*AI Boost*'} | ConvertTo-Json"
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                print(f"Error getting device info: {result.stderr}")
                return []
            
            if not result.stdout.strip():
                print("  No NPU devices found via WMI")
                return []
            
            devices = json.loads(result.stdout)
            if not isinstance(devices, list):
                devices = [devices]
            
            npu_devices = []
            for device in devices:
                device_info = {
                    'Name': device.get('Name', 'Unknown'),
                    'DeviceID': device.get('DeviceID', ''),
                    'Status': device.get('Status', ''),
                    'State': device.get('ConfigManagerErrorCode', ''),
                    'Manufacturer': device.get('Manufacturer', ''),
                    'Driver': device.get('Service', '')
                }
                npu_devices.append(device_info)
                
                print(f"  Device: {device_info['Name']}")
                print(f"    Status: {device_info['Status']}")
                print(f"    Driver: {device_info['Driver']}")
                print(f"    Manufacturer: {device_info['Manufacturer']}")
            
            return npu_devices
            
        except Exception as e:
            print(f"Error checking NPU device status: {e}")
            return []
    
    def check_intel_graphics_driver(self) -> Dict[str, str]:
        """Intel グラフィックスドライバー情報確認"""
        print("\\nChecking Intel Graphics driver information...")
        
        try:
            # Intel グラフィックス情報を取得
            result = subprocess.run([
                "powershell", "-Command",
                "Get-WmiObject -Class Win32_VideoController | Where-Object {$_.Name -like '*Intel*'} | ConvertTo-Json"
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                return {}
            
            if not result.stdout.strip():
                print("  No Intel graphics controllers found")
                return {}
            
            controllers = json.loads(result.stdout)
            if not isinstance(controllers, list):
                controllers = [controllers]
            
            for controller in controllers:
                print(f"  Graphics Controller: {controller.get('Name', 'Unknown')}")
                print(f"    Driver Version: {controller.get('DriverVersion', 'Unknown')}")
                print(f"    Driver Date: {controller.get('DriverDate', 'Unknown')}")
                print(f"    Status: {controller.get('Status', 'Unknown')}")
                
                return {
                    'Name': controller.get('Name', ''),
                    'DriverVersion': controller.get('DriverVersion', ''),
                    'DriverDate': controller.get('DriverDate', ''),
                    'Status': controller.get('Status', '')
                }
            
        except Exception as e:
            print(f"Error checking Intel graphics driver: {e}")
        
        return {}
    
    def check_npu_driver_files(self) -> List[str]:
        """NPU関連ドライバーファイルの確認"""
        print("\\nChecking for NPU driver files...")
        
        driver_locations = [
            r"C:\\Windows\\System32\\drivers",
            r"C:\\Windows\\System32\\DriverStore\\FileRepository"
        ]
        
        npu_patterns = ['*npu*', '*neural*', '*ai*', '*boost*']
        found_files = []
        
        for location in driver_locations:
            print(f"  Scanning {location}...")
            
            for pattern in npu_patterns:
                try:
                    result = subprocess.run([
                        "powershell", "-Command",
                        f"Get-ChildItem -Path '{location}' -Recurse -Include '{pattern}.sys', '{pattern}.dll', '{pattern}.inf' -ErrorAction SilentlyContinue | Select-Object FullName, Length, LastWriteTime | ConvertTo-Json"
                    ], capture_output=True, text=True, timeout=15)
                    
                    if result.returncode == 0 and result.stdout.strip():
                        try:
                            files = json.loads(result.stdout)
                            if not isinstance(files, list):
                                files = [files]
                            
                            for file_info in files:
                                file_path = file_info.get('FullName', '')
                                if file_path and 'npu' in file_path.lower():
                                    found_files.append(file_path)
                                    print(f"    Found: {file_path}")
                        except json.JSONDecodeError:
                            pass
                            
                except Exception:
                    continue
        
        if not found_files:
            print("  No NPU-specific driver files found")
        
        return found_files
    
    def check_registry_npu_entries(self) -> Dict[str, any]:
        """レジストリのNPU関連エントリ確認"""
        print("\\nChecking registry for NPU entries...")
        
        registry_paths = [
            r"HKLM\\SYSTEM\\CurrentControlSet\\Services",
            r"HKLM\\SYSTEM\\CurrentControlSet\\Control\\Class\\{4d36e968-e325-11ce-bfc1-08002be10318}",  # Display adapters
            r"HKLM\\SOFTWARE\\Intel"
        ]
        
        npu_entries = {}
        
        for reg_path in registry_paths:
            print(f"  Checking {reg_path}...")
            
            try:
                result = subprocess.run([
                    "reg", "query", reg_path, "/s", "/f", "NPU", "/t", "REG_SZ"
                ], capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0 and result.stdout.strip():
                    entries = []
                    lines = result.stdout.split('\\n')
                    current_key = ""
                    
                    for line in lines:
                        line = line.strip()
                        if line.startswith('HKEY_'):
                            current_key = line
                        elif 'NPU' in line.upper() and current_key:
                            entries.append(f"{current_key}: {line}")
                    
                    if entries:
                        npu_entries[reg_path] = entries
                        print(f"    Found {len(entries)} NPU-related entries")
                        for entry in entries[:3]:  # Show first 3
                            print(f"      {entry}")
                        if len(entries) > 3:
                            print(f"      ... and {len(entries) - 3} more")
                
            except Exception as e:
                print(f"    Error checking {reg_path}: {e}")
        
        return npu_entries
    
    def suggest_npu_activation_steps(self) -> List[str]:
        """NPU有効化手順の提案"""
        suggestions = [
            "🔧 NPU Activation Troubleshooting Steps:",
            "",
            "1. **Update Intel Graphics Driver**:",
            "   - Download latest driver from Intel website",
            "   - Ensure driver supports Intel AI Boost NPU",
            "   - Reboot after installation",
            "",
            "2. **Enable NPU in BIOS/UEFI**:",
            "   - Enter BIOS/UEFI settings during boot",
            "   - Look for 'Intel AI Boost', 'NPU', or 'Neural Processing' options",
            "   - Enable if found and save settings",
            "",
            "3. **Windows Settings**:",
            "   - Check Device Manager for NPU device status",
            "   - Update device drivers if showing warnings",
            "   - Restart Windows Update service",
            "",
            "4. **Intel Software**:",
            "   - Install Intel Arc & Iris Xe Graphics software",
            "   - Check for Intel AI acceleration settings",
            "   - Verify OpenVINO or Intel Distribution for Python support",
            "",
            "5. **Test NPU Access**:",
            "   - Run AI applications that support NPU acceleration",
            "   - Check DirectML device enumeration",
            "   - Test with Intel OpenVINO samples",
            "",
            "6. **Administrative Access**:",
            "   - Run ETW monitoring as Administrator",
            "   - Ensure proper permissions for hardware access",
            "   - Check Windows Security policies"
        ]
        
        return suggestions
    
    def comprehensive_npu_driver_investigation(self):
        """包括的NPUドライバー調査"""
        print("=" * 80)
        print(" COMPREHENSIVE NPU DRIVER & SERVICE INVESTIGATION")
        print("=" * 80)
        
        # 管理者権限確認
        is_admin = self.check_administrator_privileges()
        print(f"Administrator privileges: {'✅ Yes' if is_admin else '⚠ No (some checks may be limited)'}")
        
        # 1. NPU関連サービス確認
        print(f"\\n{'='*60}")
        print(" NPU SERVICES")
        print(f"{'='*60}")
        npu_services = self.discover_npu_services()
        self.npu_related_services = npu_services
        
        # 2. NPUデバイス状態確認
        print(f"\\n{'='*60}")
        print(" NPU DEVICES")
        print(f"{'='*60}")
        npu_devices = self.check_npu_device_status()
        self.npu_devices = npu_devices
        
        # 3. Intel グラフィックスドライバー確認
        print(f"\\n{'='*60}")
        print(" INTEL GRAPHICS DRIVER")
        print(f"{'='*60}")
        graphics_info = self.check_intel_graphics_driver()
        
        # 4. NPUドライバーファイル確認
        print(f"\\n{'='*60}")
        print(" NPU DRIVER FILES")
        print(f"{'='*60}")
        driver_files = self.check_npu_driver_files()
        
        # 5. レジストリエントリ確認
        print(f"\\n{'='*60}")
        print(" REGISTRY ENTRIES")
        print(f"{'='*60}")
        registry_entries = self.check_registry_npu_entries()
        
        # 結果サマリー
        print(f"\\n{'='*80}")
        print(" INVESTIGATION SUMMARY")
        print(f"{'='*80}")
        
        print(f"📊 Results Summary:")
        print(f"  NPU Services found: {len(npu_services)}")
        print(f"  NPU Devices found: {len(npu_devices)}")
        print(f"  Intel Graphics driver: {'✅ Found' if graphics_info else '❌ Not found'}")
        print(f"  NPU Driver files: {len(driver_files)}")
        print(f"  Registry entries: {len(registry_entries)}")
        
        # 問題診断
        issues = []
        if not npu_services:
            issues.append("No NPU-related services found")
        if not npu_devices:
            issues.append("No NPU devices detected")
        if not graphics_info:
            issues.append("Intel graphics driver not detected")
        
        if issues:
            print(f"\\n⚠ Potential Issues:")
            for issue in issues:
                print(f"  - {issue}")
        
        # NPU有効化手順の提案
        print(f"\\n{'='*60}")
        print(" NPU ACTIVATION RECOMMENDATIONS")
        print(f"{'='*60}")
        
        suggestions = self.suggest_npu_activation_steps()
        for suggestion in suggestions:
            print(suggestion)

def main():
    """メイン関数"""
    print("NPU Driver & Service Investigation")
    print("Comprehensive analysis of Intel NPU driver status and configuration")
    print()
    
    investigator = NPUDriverInvestigator()
    investigator.comprehensive_npu_driver_investigation()

if __name__ == "__main__":
    main()