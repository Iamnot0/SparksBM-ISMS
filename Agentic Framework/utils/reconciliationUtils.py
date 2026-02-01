"""
Reconciliation Utilities
Standardized logic for comparing ISMS objects and detecting drift.
"""
from typing import Dict, List, Any, Set, Tuple

# Fields to ignore during semantic comparison (system metadata)
IGNORED_FIELDS = {
    'id', 'resourceId', 'dbId', 'version', 
    'createdAt', 'updatedAt', 'createdBy', 'updatedBy',
    '_self', 'links', 'tags', 'icon'
}

def normalize_value(value: Any) -> Any:
    """Normalize values for comparison (strings, numbers, empty/none)"""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return value

def compare_dicts(obj1: Dict, obj2: Dict, ignore_fields: Set[str] = None) -> List[Dict[str, Any]]:
    """
    Compare two dictionaries and return a list of differences.
    Returns list of {'field': key, 'value1': val1, 'value2': val2}
    """
    diffs = []
    ignore = IGNORED_FIELDS.union(ignore_fields or set())
    
    all_keys = set(obj1.keys()) | set(obj2.keys())
    
    for key in all_keys:
        if key in ignore:
            continue
            
        val1 = normalize_value(obj1.get(key))
        val2 = normalize_value(obj2.get(key))
        
        # specific handling for complex types (nested dicts/lists) could go here
        # for now, we treat them as values
        if val1 != val2:
            diffs.append({
                'field': key,
                'value1': val1,
                'value2': val2
            })
            
    return diffs

def calculate_drift_score(total_objects: int, missing_count: int, diff_count: int) -> float:
    """Calculate a 'Drift Score' (0.0 to 1.0, where 0 is perfect sync)"""
    if total_objects == 0:
        return 0.0
    
    # Weight missing objects higher than modified objects
    weighted_diff = (missing_count * 1.0) + (diff_count * 0.5)
    score = min(1.0, weighted_diff / total_objects)
    return round(score, 4)
