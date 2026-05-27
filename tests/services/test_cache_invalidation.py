import sys
from unittest.mock import MagicMock, patch

# Dynamically mock the 'redis' module for environment compatibility if not installed
try:
    import redis
except ImportError:
    mock_redis = MagicMock()
    sys.modules["redis"] = mock_redis

import pytest
from app.core.perf_cache import HybridCache, InMemoryCache, RedisCache

def test_hybrid_cache_operations():
    redis_url = "redis://localhost:6379"
    with patch("redis.from_url") as mock_from_url:
        mock_client = MagicMock()
        mock_from_url.return_value = mock_client
        
        cache = HybridCache(redis_url)
        
        assert isinstance(cache.l1, InMemoryCache)
        assert isinstance(cache.l2, RedisCache)
        
        key = ("test_key",)
        value = "test_value"
        cache.set(key, value, ttl=10, fingerprint=f"v:{cache.cache_generation()}")
        
        assert cache.l1.get(key) == value
        mock_client.setex.assert_called_once()
        
        assert cache.get(key) == value
        
        cache.l1.clear()
        assert cache.l1.get(key) is None
        
        import pickle
        mock_client.get.return_value = pickle.dumps({"value": "from_l2", "fingerprint": "v:1"})
        with patch.object(cache.l2, "cache_generation", return_value=1):
            assert cache.get(key) == "from_l2"
            assert cache.l1.get(key) == "from_l2"
