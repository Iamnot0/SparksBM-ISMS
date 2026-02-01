"""
Prompt Versioning and Evaluation Framework

Tracks prompt versions, evaluates performance, and enables A/B testing.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class PromptVersion:
    """Represents a versioned prompt"""
    prompt_id: str
    version: str
    component: str  # e.g., "mcp_server", "intent_classifier"
    prompt_text: str
    created_at: str
    metadata: Dict[str, Any]
    performance_metrics: Optional[Dict[str, float]] = None


@dataclass
class PromptEvaluation:
    """Represents an evaluation of a prompt"""
    evaluation_id: str
    prompt_id: str
    version: str
    test_cases: List[Dict[str, Any]]
    results: Dict[str, Any]
    evaluated_at: str
    success_rate: float
    avg_response_time: Optional[float] = None


class PromptVersionManager:
    """Manages prompt versions and evaluations"""
    
    def __init__(self, storage_path: Optional[Path] = None):
        """
        Initialize prompt version manager.
        
        Args:
            storage_path: Path to store version data (default: Agentic Framework/utils/prompt_versions/)
        """
        if storage_path is None:
            base_path = Path(__file__).parent
            storage_path = base_path / "prompt_versions"
        
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        self.versions_file = self.storage_path / "versions.json"
        self.evaluations_file = self.storage_path / "evaluations.json"
        
        # Load existing data
        self.versions: Dict[str, List[PromptVersion]] = self._load_versions()
        self.evaluations: List[PromptEvaluation] = self._load_evaluations()
    
    def _load_versions(self) -> Dict[str, List[PromptVersion]]:
        """Load prompt versions from storage"""
        if not self.versions_file.exists():
            return {}
        
        try:
            with open(self.versions_file, 'r') as f:
                data = json.load(f)
            
            versions = {}
            for component, version_list in data.items():
                versions[component] = [
                    PromptVersion(**v) for v in version_list
                ]
            return versions
        except Exception as e:
            logger.warning(f"Failed to load prompt versions: {e}")
            return {}
    
    def _load_evaluations(self) -> List[PromptEvaluation]:
        """Load evaluations from storage"""
        if not self.evaluations_file.exists():
            return []
        
        try:
            with open(self.evaluations_file, 'r') as f:
                data = json.load(f)
            return [PromptEvaluation(**e) for e in data]
        except Exception as e:
            logger.warning(f"Failed to load evaluations: {e}")
            return []
    
    def _save_versions(self):
        """Save prompt versions to storage"""
        try:
            data = {}
            for component, version_list in self.versions.items():
                data[component] = [asdict(v) for v in version_list]
            
            with open(self.versions_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save prompt versions: {e}")
    
    def _save_evaluations(self):
        """Save evaluations to storage"""
        try:
            data = [asdict(e) for e in self.evaluations]
            with open(self.evaluations_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save evaluations: {e}")
    
    def register_prompt(
        self,
        component: str,
        prompt_text: str,
        prompt_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> PromptVersion:
        """
        Register a new prompt version.
        
        Args:
            component: Component name (e.g., "mcp_server")
            prompt_text: The prompt text
            prompt_id: Optional ID (auto-generated if not provided)
            metadata: Optional metadata (author, description, etc.)
        
        Returns:
            PromptVersion object
        """
        if prompt_id is None:
            prompt_id = f"{component}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Determine version number
        if component not in self.versions:
            self.versions[component] = []
            version = "1.0.0"
        else:
            # Increment patch version
            last_version = self.versions[component][-1].version
            parts = last_version.split('.')
            patch = int(parts[2]) + 1
            version = f"{parts[0]}.{parts[1]}.{patch}"
        
        prompt_version = PromptVersion(
            prompt_id=prompt_id,
            version=version,
            component=component,
            prompt_text=prompt_text,
            created_at=datetime.now().isoformat(),
            metadata=metadata or {}
        )
        
        self.versions[component].append(prompt_version)
        self._save_versions()
        
        logger.info(f"Registered prompt version: {component} v{version}")
        return prompt_version
    
    def get_latest_version(self, component: str) -> Optional[PromptVersion]:
        """Get the latest version of a prompt for a component"""
        if component not in self.versions or not self.versions[component]:
            return None
        return self.versions[component][-1]
    
    def evaluate_prompt(
        self,
        prompt_id: str,
        version: str,
        test_cases: List[Dict[str, Any]],
        results: Dict[str, Any],
        success_rate: float,
        avg_response_time: Optional[float] = None
    ) -> PromptEvaluation:
        """
        Record an evaluation of a prompt version.
        
        Args:
            prompt_id: ID of the prompt
            version: Version string
            test_cases: List of test cases used
            results: Evaluation results
            success_rate: Success rate (0.0-1.0)
            avg_response_time: Average response time in seconds
        
        Returns:
            PromptEvaluation object
        """
        evaluation = PromptEvaluation(
            evaluation_id=f"eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            prompt_id=prompt_id,
            version=version,
            test_cases=test_cases,
            results=results,
            evaluated_at=datetime.now().isoformat(),
            success_rate=success_rate,
            avg_response_time=avg_response_time
        )
        
        self.evaluations.append(evaluation)
        self._save_evaluations()
        
        for component, version_list in self.versions.items():
            for v in version_list:
                if v.prompt_id == prompt_id and v.version == version:
                    if v.performance_metrics is None:
                        v.performance_metrics = {}
                    v.performance_metrics['last_success_rate'] = success_rate
                    v.performance_metrics['last_evaluated'] = evaluation.evaluated_at
                    if avg_response_time:
                        v.performance_metrics['avg_response_time'] = avg_response_time
                    break
        
        self._save_versions()
        logger.info(f"Recorded evaluation for {prompt_id} v{version}: {success_rate:.2%} success rate")
        return evaluation
    
    def get_best_version(self, component: str) -> Optional[PromptVersion]:
        """Get the best performing version for a component"""
        if component not in self.versions:
            return None
        
        best = None
        best_score = 0.0
        
        for version in self.versions[component]:
            if version.performance_metrics:
                score = version.performance_metrics.get('last_success_rate', 0.0)
                if score > best_score:
                    best_score = score
                    best = version
        
        return best if best else self.get_latest_version(component)
    
    def get_evaluation_history(self, prompt_id: Optional[str] = None) -> List[PromptEvaluation]:
        """Get evaluation history, optionally filtered by prompt_id"""
        if prompt_id:
            return [e for e in self.evaluations if e.prompt_id == prompt_id]
        return self.evaluations


# Global instance
_version_manager: Optional[PromptVersionManager] = None


def get_version_manager() -> PromptVersionManager:
    """Get or create the global prompt version manager"""
    global _version_manager
    if _version_manager is None:
        _version_manager = PromptVersionManager()
    return _version_manager


def register_prompt_version(
    component: str,
    prompt_text: str,
    prompt_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> PromptVersion:
    """Convenience function to register a prompt version"""
    return get_version_manager().register_prompt(component, prompt_text, prompt_id, metadata)
