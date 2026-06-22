"""
CyberLens — Neo4j Connection Manager
=======================================
Manages Neo4j connection pool with retry logic, health checks,
and graceful degradation when graph DB is unavailable.

URI from .env: NEO4J_URI=bolt://localhost:7687
Credentials: NEO4J_USER, NEO4J_PASSWORD

Author: CyberLens Team — GPCSSI Internship
"""

import logging
import os
import time
from contextlib import contextmanager
from typing import Any, Dict, Generator, List, Optional

logger = logging.getLogger("cyberlens.graph.neo4j")

# Neo4j driver loaded lazily to avoid hard import failure
_driver = None
_AVAILABLE = False


def _get_driver():
    """Lazy-load Neo4j driver and return it. Returns None if unavailable."""
    global _driver, _AVAILABLE

    if _driver is not None:
        return _driver

    try:
        from neo4j import GraphDatabase, exceptions as neo4j_exc

        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "cyberlens2025")

        _driver = GraphDatabase.driver(
            uri, auth=(user, password),
            max_connection_pool_size=50,
            connection_timeout=5,
            max_transaction_retry_time=10,
        )
        # Verify connectivity
        _driver.verify_connectivity()
        _AVAILABLE = True
        logger.info("Neo4j connected: %s", uri)
        return _driver

    except ImportError:
        logger.warning("neo4j package not installed — graph features disabled. "
                       "Install: pip install neo4j")
    except Exception as e:
        logger.warning("Neo4j unavailable (%s) — graph features disabled. "
                       "Start Neo4j: docker-compose up neo4j", e)

    _AVAILABLE = False
    return None


def is_available() -> bool:
    """Check if Neo4j is available."""
    global _AVAILABLE
    if _driver is not None:
        return _AVAILABLE
    _get_driver()
    return _AVAILABLE


def close() -> None:
    """Close the Neo4j driver."""
    global _driver, _AVAILABLE
    if _driver:
        _driver.close()
        _driver = None
        _AVAILABLE = False
        logger.info("Neo4j driver closed")


@contextmanager
def get_session() -> Generator:
    """Context manager for a Neo4j session.

    Yields None silently if Neo4j is unavailable.
    """
    driver = _get_driver()
    if driver is None:
        yield None
        return

    session = driver.session()
    try:
        yield session
    except Exception as e:
        logger.error("Neo4j session error: %s", e)
        raise
    finally:
        session.close()


def run_query(
    cypher: str,
    params: Optional[Dict[str, Any]] = None,
    retries: int = 3,
) -> List[Dict[str, Any]]:
    """Run a Cypher query with retry logic.

    Args:
        cypher: Cypher query string.
        params: Query parameters.
        retries: Number of retry attempts.

    Returns:
        List of record dicts, empty list if Neo4j unavailable.
    """
    params = params or {}

    for attempt in range(retries):
        with get_session() as session:
            if session is None:
                return []
            try:
                result = session.run(cypher, **params)
                return [dict(record) for record in result]
            except Exception as e:
                if attempt < retries - 1:
                    wait = 2 ** attempt
                    logger.warning("Neo4j query failed (attempt %d/%d): %s — retrying in %ds",
                                   attempt + 1, retries, e, wait)
                    time.sleep(wait)
                else:
                    logger.error("Neo4j query failed after %d retries: %s", retries, e)
                    return []


def run_write(cypher: str, params: Optional[Dict[str, Any]] = None) -> bool:
    """Run a write Cypher query.

    Returns:
        True if successful, False if Neo4j unavailable or error.
    """
    params = params or {}
    with get_session() as session:
        if session is None:
            return False
        try:
            session.run(cypher, **params)
            return True
        except Exception as e:
            logger.error("Neo4j write failed: %s", e)
            return False


def health_check() -> Dict[str, Any]:
    """Check Neo4j health and return status dict."""
    driver = _get_driver()
    if driver is None:
        return {"status": "unavailable", "connected": False}

    try:
        result = run_query("RETURN 1 AS ping")
        if result and result[0].get("ping") == 1:
            return {
                "status": "healthy",
                "connected": True,
                "uri": os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            }
    except Exception as e:
        return {"status": "error", "connected": False, "error": str(e)}

    return {"status": "unknown", "connected": False}


def create_constraints() -> None:
    """Create uniqueness constraints and indexes for all node types."""
    constraints = [
        "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Channel) REQUIRE c.id IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (p:PhoneNumber) REQUIRE p.value IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (u:UPIId) REQUIRE u.value IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (t:TelegramUser) REQUIRE t.username IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (s:ScamCampaign) REQUIRE s.id IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (i:Image) REQUIRE i.hash IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (d:Domain) REQUIRE d.url IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (q:QRCode) REQUIRE q.decoded_value IS UNIQUE",
    ]
    indexes = [
        "CREATE INDEX IF NOT EXISTS FOR (c:Channel) ON (c.risk_score)",
        "CREATE INDEX IF NOT EXISTS FOR (s:ScamCampaign) ON (s.risk_level)",
        "CREATE INDEX IF NOT EXISTS FOR (p:PhoneNumber) ON (p.flag_count)",
    ]
    for cypher in constraints + indexes:
        run_write(cypher)
    logger.info("Neo4j constraints and indexes created")
