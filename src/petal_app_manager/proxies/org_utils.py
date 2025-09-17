"""
Organization ID utility functions
=================================

Provides utility functions for getting organization ID from either the
OrganizationManager (preferred) or LocalDBProxy (fallback).
"""

from typing import Optional
import logging

def get_organization_id_from_any_source(local_db_proxy=None) -> Optional[str]:
    """
    Get organization ID from any available source.
    
    Priority:
    1. OrganizationManager (file-based)
    2. LocalDBProxy (database-based, fallback)
    
    Args:
        local_db_proxy: Optional LocalDBProxy instance for fallback
        
    Returns:
        Organization ID if available from any source, None otherwise
    """
    log = logging.getLogger("OrganizationUtils")
    
    # Try OrganizationManager first
    try:
        from ..organization_manager import get_organization_manager
        org_manager = get_organization_manager()
        org_id = org_manager.organization_id
        if org_id:
            log.debug(f"Got organization ID from OrganizationManager: {org_id}")
            return org_id
    except Exception as e:
        log.debug(f"Could not get organization ID from OrganizationManager: {e}")
    
    # Fallback to LocalDBProxy if available
    if local_db_proxy:
        try:
            org_id = local_db_proxy.organization_id
            if org_id:
                log.debug(f"Got organization ID from LocalDBProxy fallback: {org_id}")
                return org_id
        except Exception as e:
            log.debug(f"Could not get organization ID from LocalDBProxy: {e}")
    
    log.debug("Organization ID not available from any source")
    return None
