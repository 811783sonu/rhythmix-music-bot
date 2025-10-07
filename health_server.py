from aiohttp import web
import asyncio
import logging
from datetime import datetime
from config import HEALTH_CHECK_PORT, ENABLE_HEALTH_CHECK

logger = logging.getLogger(__name__)

class HealthCheckServer:
    def __init__(self):
        self.app = web.Application()
        self.runner = None
        self.site = None
        self.start_time = datetime.now()
        self.setup_routes()
    
    def setup_routes(self):
        """Setup health check routes"""
        self.app.router.add_get('/health', self.health_check)
        self.app.router.add_get('/ping', self.ping)
        self.app.router.add_get('/', self.root)
    
    async def health_check(self, request):
        """Health check endpoint for hosting platforms"""
        uptime = datetime.now() - self.start_time
        return web.json_response({
            'status': 'healthy',
            'uptime': str(uptime).split('.')[0],
            'timestamp': datetime.now().isoformat()
        })
    
    async def ping(self, request):
        """Simple ping endpoint"""
        return web.Response(text='pong')
    
    async def root(self, request):
        """Root endpoint"""
        uptime = datetime.now() - self.start_time
        return web.Response(
            text=f"🎵 Music Bot is running!\n⏰ Uptime: {str(uptime).split('.')[0]}",
            content_type='text/plain'
        )
    
    async def start(self):
        """Start the health check server"""
        if not ENABLE_HEALTH_CHECK:
            logger.info("Health check server disabled")
            return
        
        try:
            self.runner = web.AppRunner(self.app)
            await self.runner.setup()
            self.site = web.TCPSite(self.runner, '0.0.0.0', HEALTH_CHECK_PORT)
            await self.site.start()
            logger.info(f"Health check server started on port {HEALTH_CHECK_PORT}")
        except Exception as e:
            logger.error(f"Failed to start health check server: {e}")
    
    async def stop(self):
        """Stop the health check server"""
        if self.site:
            await self.site.stop()
        if self.runner:
            await self.runner.cleanup()
        logger.info("Health check server stopped")

# Global instance
health_server = HealthCheckServer()