#!/usr/bin/env python3
"""
Test script for agent planning and validation system.

This script tests that agents properly:
1. Plan before answering
2. Select appropriate tools
3. Validate answers
4. Retry if needed
"""

import sys
import logging
from typing import Optional

# Setup logging to see planning steps
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_agent_planning(
    question: str, 
    agent_name: str = "cypher",
    session_id: Optional[str] = None
) -> dict:
    """
    Test agent planning and validation.
    
    Args:
        question: The question to test
        agent_name: Which agent to test
        session_id: Optional session ID
        
    Returns:
        dict with response and metadata
    """
    try:
        from agents import generate_response, get_agent_factory
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Testing Agent: {agent_name}")
        logger.info(f"Question: {question}")
        logger.info(f"{'='*60}")
        
        # Get factory to inspect agent config
        factory = get_agent_factory()
        agent_config = factory.get_agent(agent_name)
        
        logger.info(f"Max Iterations: {agent_config.get('max_iterations', 'default')}")
        logger.info(f"Tools: {[t.get('name') for t in agent_config.get('tools', [])]}")
        logger.info(f"\nGenerating response with planning and validation...\n")
        
        # Generate response (will show planning steps if verbose=True)
        response = generate_response(
            question,
            agent_name=agent_name,
            session_id=session_id
        )
        
        logger.info(f"\n{'='*60}")
        logger.info("RESPONSE:")
        logger.info(f"{'='*60}\n{response}\n")
        
        return {
            "success": True,
            "agent": agent_name,
            "question": question,
            "response": response,
            "config": {
                "max_iterations": agent_config.get('max_iterations'),
                "tools": [t.get('name') for t in agent_config.get('tools', [])]
            }
        }
        
    except ImportError as e:
        logger.error(f"Import error: {e}")
        logger.error("Make sure you're in the project directory and dependencies are installed")
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"Error testing agent: {e}")
        return {"success": False, "error": str(e)}


def run_tests():
    """Run planning and validation tests."""
    
    test_cases = [
        {
            "question": "What are the main topics in the documents?",
            "agent": "chat",
            "description": "Simple chat - tests basic planning"
        },
        {
            "question": "Find documents related to specific entities",
            "agent": "vector",
            "description": "Vector search - tests semantic planning"
        },
        {
            "question": "What relationships exist between different topics?",
            "agent": "cypher",
            "description": "Cypher - tests multi-tool planning"
        }
    ]
    
    results = []
    
    for i, test in enumerate(test_cases, 1):
        logger.info(f"\n\n{'#'*60}")
        logger.info(f"Test {i}/{len(test_cases)}: {test['description']}")
        logger.info(f"{'#'*60}")
        
        result = test_agent_planning(
            question=test['question'],
            agent_name=test['agent'],
            session_id=f"test_session_{i}"
        )
        
        results.append(result)
        
        if not result.get('success'):
            logger.error(f"Test {i} FAILED: {result.get('error')}")
        else:
            logger.info(f"Test {i} SUCCESS")
    
    # Summary
    logger.info(f"\n\n{'='*60}")
    logger.info("TEST SUMMARY")
    logger.info(f"{'='*60}")
    
    successful = sum(1 for r in results if r.get('success'))
    total = len(results)
    
    logger.info(f"Passed: {successful}/{total}")
    
    for i, result in enumerate(results, 1):
        status = "✓ PASS" if result.get('success') else "✗ FAIL"
        logger.info(f"{status}: Test {i} - {test_cases[i-1]['description']}")
    
    return all(r.get('success') for r in results)


def test_all_agents():
    """Test all enabled agents."""
    try:
        from agents import get_agent_factory
        
        factory = get_agent_factory()
        enabled_agents = factory.get_enabled_agents()
        
        logger.info(f"\nTesting all {len(enabled_agents)} enabled agents...")
        logger.info(f"Agents: {enabled_agents}\n")
        
        question = "What is the purpose of these documents?"
        
        for agent in enabled_agents:
            result = test_agent_planning(question, agent_name=agent)
            status = "✓" if result.get('success') else "✗"
            logger.info(f"{status} Agent '{agent}' - "
                       f"iterations: {result.get('config', {}).get('max_iterations')}")
            
    except Exception as e:
        logger.error(f"Error testing all agents: {e}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Test agent planning and validation system"
    )
    parser.add_argument(
        "--question",
        type=str,
        help="Custom question to test"
    )
    parser.add_argument(
        "--agent",
        type=str,
        default="cypher",
        choices=["chat", "vector", "cypher", "full", "scoped"],
        help="Agent to test"
    )
    parser.add_argument(
        "--all-agents",
        action="store_true",
        help="Test all enabled agents"
    )
    parser.add_argument(
        "--full-tests",
        action="store_true",
        help="Run full test suite"
    )
    
    args = parser.parse_args()
    
    if args.all_agents:
        test_all_agents()
    elif args.question:
        result = test_agent_planning(args.question, agent_name=args.agent)
        if not result.get('success'):
            sys.exit(1)
    elif args.full_tests:
        success = run_tests()
        sys.exit(0 if success else 1)
    else:
        # Default: test one question with each agent type
        test_all_agents()
