#!/usr/bin/env python3
import asyncio
import socket
import time
import ssl
import aiohttp
import os
import sys
import json
from datetime import datetime
from urllib.parse import urlparse
from typing import Dict, Any, Optional

# Config
BOT_TOKEN = os.getenv('BOT_TOKEN', '')
VLESS_CONFIG = os.getenv('VLESS_CONFIG', '')
CHAT_IDS = os.getenv('CHAT_IDS', '').split(',') if os.getenv('CHAT_IDS') else []
MODE = os.getenv('MODE', 'web').lower()

class VLESSChecker:
    def __init__(self, config_str: str):
        self.config = self.parse_config(config_str)
    
    def parse_config(self, config_str: str) -> Optional[Dict]:
        try:
            if not config_str.startswith('vless://'):
                return None
            
            config_str = config_str[8:]
            if '@' not in config_str:
                return None
            
            uuid_part, rest = config_str.split('@', 1)
            
            if '#' in rest:
                server_part, name = rest.rsplit('#', 1)
            else:
                server_part, name = rest, "Unknown"
            
            if '?' in server_part:
                address_part, params_part = server_part.split('?', 1)
            else:
                address_part, params_part = server_part, ""
            
            if ':' in address_part:
                host, port = address_part.rsplit(':', 1)
                port = int(port)
            else:
                host, port = address_part, 443
            
            params = {}
            if params_part:
                for param in params_part.split('&'):
                    if '=' in param:
                        key, value = param.split('=', 1)
                        params[key] = value
            
            return {
                'uuid': uuid_part,
                'host': host,
                'port': port,
                'name': name,
                'security': params.get('security', 'none'),
                'type': params.get('type', 'tcp'),
                'sni': params.get('sni', ''),
                'flow': params.get('flow', '')
            }
        except:
            return None
    
    async def check_dns(self):
        try:
            if not self.config:
                return False, "Config parse error"
            
            host = self.config['host']
            start = time.time()
            result = await asyncio.get_event_loop().getaddrinfo(host, None)
            end = time.time()
            
            ip = result[0][4][0]
            dns_time = round((end - start) * 1000, 2)
            return True, f"DNS resolved ({dns_time}ms): {ip}"
        except Exception as e:
            return False, f"DNS error: {str(e)}"
    
    async def check_geo(self):
        try:
            if not self.config:
                return False, "Config parse error"
            
            host = self.config['host']
            result = await asyncio.get_event_loop().getaddrinfo(host, None)
            ip = result[0][4][0]
            
            async with aiohttp.ClientSession() as session:
                url = f"http://ip-api.com/json/{ip}"
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        country = data.get('country', 'N/A')
                        city = data.get('city', 'N/A')
                        isp = data.get('isp', 'N/A')
                        return True, f"Location: {country}, {city} ({isp})"
                    else:
                        return False, f"Geo API error: {response.status}"
        except Exception as e:
            return False, f"Geo error: {str(e)}"
    
    async def check_tcp(self):
        try:
            if not self.config:
                return False, "Config parse error"
            
            host = self.config['host']
            port = self.config['port']
            
            start = time.time()
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=10
            )
            end = time.time()
            
            tcp_time = round((end - start) * 1000, 2)
            writer.close()
            await writer.wait_closed()
            
            return True, f"TCP connection OK ({tcp_time}ms)"
        except Exception as e:
            return False, f"TCP error: {str(e)}"
    
    async def check_http(self):
        try:
            test_urls = ["https://www.google.com", "https://httpbin.org/ip"]
            results = []
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                for url in test_urls:
                    try:
                        start = time.time()
                        async with session.get(url) as response:
                            end = time.time()
                            request_time = round((end - start) * 1000, 2)
                            if response.status == 200:
                                results.append(f"✅ {urlparse(url).netloc} ({request_time}ms)")
                            else:
                                results.append(f"❌ {urlparse(url).netloc} ({response.status})")
                    except:
                        results.append(f"❌ {urlparse(url).netloc} (failed)")
            
            success_count = len([r for r in results if r.startswith('✅')])
            return success_count > 0, f"HTTP tests ({success_count}/{len(results)}): " + ", ".join(results)
        except Exception as e:
            return False, f"HTTP error: {str(e)}"
    
    async def run_check(self):
        print("Running VLESS check...")
        
        results = {
            'success': False,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'server': f"{self.config['host']}:{self.config['port']}" if self.config else "N/A",
            'checks': {},
            'overall_status': 'FAILED',
            'success_rate': '0/0'
        }
        
        if not self.config:
            results['checks']['config'] = {'success': False, 'message': 'VLESS config parse error'}
            return results
        
        # Run checks
        dns_ok, dns_msg = await self.check_dns()
        results['checks']['dns'] = {'success': dns_ok, 'message': dns_msg}
        
        geo_ok, geo_msg = await self.check_geo()
        results['checks']['geo'] = {'success': geo_ok, 'message': geo_msg}
        
        tcp_ok, tcp_msg = await self.check_tcp()
        results['checks']['tcp'] = {'success': tcp_ok, 'message': tcp_msg}
        
        http_ok, http_msg = await self.check_http()
        results['checks']['http'] = {'success': http_ok, 'message': http_msg}
        
        # Calculate results
        critical_checks = [dns_ok, tcp_ok, http_ok]
        results['success'] = all(critical_checks)
        results['overall_status'] = 'OK' if results['success'] else 'FAILED'
        
        all_checks = [dns_ok, geo_ok, tcp_ok, http_ok]
        success_count = sum(all_checks)
        results['success_rate'] = f"{success_count}/{len(all_checks)}"
        
        return results

class TelegramClient:
    def __init__(self, token: str):
        self.token = token
        self.base_url = f"https://api.telegram.org/bot{token}"
    
    async def send_message(self, chat_id: str, text: str) -> bool:
        try:
            url = f"{self.base_url}/sendMessage"
            data = {
                'chat_id': chat_id,
                'text': text,
                'parse_mode': 'HTML'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data, timeout=30) as response:
                    return response.status == 200
        except:
            return False

def format_report(results: Dict[str, Any]) -> str:
    status_emoji = "✅" if results['success'] else "❌"
    report = f"🔍 <b>VLESS Check Report</b>\n\n"
    report += f"{status_emoji} <b>Status:</b> {results['overall_status']}\n"
    report += f"📊 <b>Success:</b> {results['success_rate']}\n"
    report += f"🕐 <b>Time:</b> {results['timestamp']}\n"
    report += f"🌐 <b>Server:</b> {results['server']}\n\n"
    
    checks = results['checks']
    for check_name, check_data in checks.items():
        emoji = "✅" if check_data['success'] else "❌"
        msg = check_data['message'].split('\n')[0]  # First line only
        report += f"{emoji} <b>{check_name.upper()}:</b> {msg}\n"
    
    return report

async def send_telegram_reports():
    if not BOT_TOKEN or not CHAT_IDS:
        print("❌ BOT_TOKEN or CHAT_IDS not set")
        return
    
    if not VLESS_CONFIG:
        print("❌ VLESS_CONFIG not set")
        return
    
    checker = VLESSChecker(VLESS_CONFIG)
    results = await checker.run_check()
    
    report = format_report(results)
    telegram = TelegramClient(BOT_TOKEN)
    
    success_count = 0
    for chat_id in CHAT_IDS:
        chat_id = chat_id.strip()
        if chat_id:
            if await telegram.send_message(chat_id, report):
                success_count += 1
            await asyncio.sleep(1)
    
    print(f"📤 Report sent to {success_count}/{len(CHAT_IDS)} chats")

async def run_web_service():
    try:
        from fastapi import FastAPI
        import uvicorn
        
        app = FastAPI(title="VLESS Checker")
        
        if not VLESS_CONFIG:
            print("❌ VLESS_CONFIG not set")
            return
        
        checker = VLESSChecker(VLESS_CONFIG)
        
        @app.get("/")
        async def root():
            return {"service": "VLESS Checker", "status": "running"}
        
        @app.get("/health")
        async def health():
            return {"status": "healthy", "timestamp": datetime.now().isoformat()}
        
        @app.get("/check")
        async def check():
            return await checker.run_check()
        
        port = int(os.getenv("PORT", 8000))
        print(f"🚀 Starting web service on port {port}")
        
        uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
        
    except ImportError:
        print("❌ FastAPI not installed")
    except Exception as e:
        print(f"❌ Web service error: {e}")

async def main():
    if MODE == 'web':
        await run_web_service()
    elif MODE == 'telegram':
        await send_telegram_reports()
    else:
        if not VLESS_CONFIG:
            print("❌ VLESS_CONFIG not set")
            return
        
        checker = VLESSChecker(VLESS_CONFIG)
        results = await checker.run_check()
        
        print(f"\n📊 VLESS CHECK RESULTS")
        print(f"Status: {results['overall_status']}")
        print(f"Success: {results['success_rate']}")
        print(f"Server: {results['server']}")
        print(f"Time: {results['timestamp']}")
        
        print(f"\n🔍 DETAILS:")
        for name, data in results['checks'].items():
            emoji = "✅" if data['success'] else "❌"
            print(f"{emoji} {name.upper()}: {data['message']}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Stopped")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
