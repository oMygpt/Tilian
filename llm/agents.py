"""
Multi-Agent Question Generation Logic
"""

import json
import math
from typing import List, Dict, Any
from llm.router import llm_client
from llm import agent_prompts
from llm.prompts import parse_llm_response, format_prompt

class MultiAgentGenerator:
    """
    Orchestrates the multi-agent workflow for question generation.
    """
    
    def __init__(self):
        self.client = llm_client
        from database import db
        self.db = db

    def analyze_content(self, content: str, workflow_id: str, chapter_id: int, model_id: str = None) -> List[Dict[str, Any]]:
        """
        Agent A: Analyze content to extract contexts.
        """
        print("Agent A: Analyzing content...")
        prompt = format_prompt(agent_prompts.ANALYZER_PROMPT, chapter_content=content[:15000]) # Truncate if too long
        
        # Log input
        self.db.create_agent_log(workflow_id, chapter_id, 'Agent A', 'Input', input_data=prompt)
        
        response = self.client.generate_text(prompt, provider_id=model_id)
        active_model_id = self.client.get_active_model_id(model_id)
        
        # Log output
        self.db.create_agent_log(workflow_id, chapter_id, 'Agent A', 'Output', output_data=response, model_name=active_model_id)
        
        try:
            contexts = parse_llm_response(response)
            return contexts
        except Exception as e:
            print(f"Agent A failed: {e}")
            self.db.create_agent_log(workflow_id, chapter_id, 'Agent A', 'Error', output_data=str(e))
            return []

    def generate_initial_items(self, contexts: List[Dict[str, Any]], count: int, item_type: str, workflow_id: str, chapter_id: int, model_id: str = None) -> List[Dict[str, Any]]:
        """
        Agent B: Generate initial items based on contexts.
        """
        print(f"Agent B: Generating {count} items ({item_type})...")
        items = []
        
        if not contexts:
            return []
            
        # Distribute count among contexts
        items_per_context = math.ceil(count / len(contexts))
        
        for i, context in enumerate(contexts):
            if len(items) >= count:
                break
                
            topic = context.get('Topic', 'General')
            concepts = ", ".join(context.get('Key_Concepts', []))
            source_text = context.get('Source_Text', '')
            
            # Select prompt based on type
            if item_type == 'qa': 
                # Use MCQ prompt for QA as per design, but we'll need to adapt the output
                prompt_template = agent_prompts.GENERATOR_MCQ_PROMPT
            else: # exercise
                prompt_template = agent_prompts.GENERATOR_EXERCISE_PROMPT
            
            prompt = format_prompt(
                prompt_template,
                count=items_per_context,
                topic=topic,
                concepts=concepts,
                source_text=source_text
            )
            
            # Log input
            self.db.create_agent_log(workflow_id, chapter_id, 'Agent B', f'Input (Context {i})', input_data=prompt)
            
            try:
                response = self.client.generate_text(prompt, provider_id=model_id)
                active_model_id = self.client.get_active_model_id(model_id)
                
                # Log output
                self.db.create_agent_log(workflow_id, chapter_id, 'Agent B', f'Output (Context {i})', output_data=response, model_name=active_model_id)
                
                batch_items = parse_llm_response(response)
                
                # Normalize items
                for item in batch_items:
                    # Ensure type is set for exercises
                    if item_type == 'exercise' and 'type' not in item:
                        item['type'] = 'essay' # Default
                    
                    # For QA mode, if it's MCQ, format it for the QA table
                    if item_type == 'qa':
                        # If it has options, append them to the question or handle them
                        if 'options' in item:
                            options_str = "\n".join(item['options']) if isinstance(item['options'], list) else str(item['options'])
                            # We'll store the MCQ structure in the question text for now, 
                            # as the QA table is simple (Q, A, Expl).
                            # Alternatively, we could map this to 'exercise' type if the user wanted exercises.
                            # But since they asked for QA, we'll format it as a Q&A pair.
                            item['question'] = f"{item['question']}\n\nOptions:\n{options_str}"
                            # Keep options in item for potential future use or debugging
                        
                    items.append(item)
                    if len(items) >= count:
                        break
            except Exception as e:
                print(f"Agent B failed for context {topic}: {e}")
                self.db.create_agent_log(workflow_id, chapter_id, 'Agent B', f'Error (Context {i})', output_data=str(e))
                continue
                
        return items[:count]

    def review_items(self, items: List[Dict[str, Any]], workflow_id: str, chapter_id: int, model_id: str = None) -> List[Dict[str, Any]]:
        """
        Agent C: Review items.
        """
        print("Agent C: Reviewing items...")
        # Review in batches to avoid context limit
        reviews = []
        batch_size = 5
        
        for i in range(0, len(items), batch_size):
            batch = items[i:i+batch_size]
            # Add index to help agent identify items
            batch_with_index = []
            for idx, item in enumerate(batch):
                item_copy = item.copy()
                item_copy['item_index'] = idx # Local index 0-4
                batch_with_index.append(item_copy)
            
            prompt = format_prompt(
                agent_prompts.REVIEWER_PROMPT,
                items_json=json.dumps(batch_with_index, ensure_ascii=False, indent=2)
            )
            
            # Log input
            self.db.create_agent_log(workflow_id, chapter_id, 'Agent C', f'Input (Batch {i})', input_data=prompt)
            
            try:
                response = self.client.generate_text(prompt, provider_id=model_id)
                active_model_id = self.client.get_active_model_id(model_id)
                
                # Log output
                self.db.create_agent_log(workflow_id, chapter_id, 'Agent C', f'Output (Batch {i})', output_data=response, model_name=active_model_id)
                
                batch_reviews = parse_llm_response(response)
                
                # Adjust index to global
                for review in batch_reviews:
                    review['global_index'] = i + review.get('item_index', 0)
                    reviews.append(review)
            except Exception as e:
                print(f"Agent C failed for batch {i}: {e}")
                self.db.create_agent_log(workflow_id, chapter_id, 'Agent C', f'Error (Batch {i})', output_data=str(e))
                
        return reviews

    def refine_items(self, items: List[Dict[str, Any]], reviews: List[Dict[str, Any]], workflow_id: str, chapter_id: int, model_id: str = None) -> List[Dict[str, Any]]:
        """
        Agent D: Refine items based on reviews.
        """
        print("Agent D: Refining items...")
        refined_items = items.copy()
        
        for review in reviews:
            rating = review.get('rating', 3)
            idx = review.get('global_index')
            
            if idx is None or idx >= len(items):
                continue
                
            if rating < 3: # Neutral or Dissatisfied
                print(f"Refining item {idx} (Rating: {rating})...")
                original_item = items[idx]
                critique = review.get('critique', '')
                suggestion = review.get('suggestion', '')
                
                prompt = format_prompt(
                    agent_prompts.REFINER_PROMPT,
                    original_item=json.dumps(original_item, ensure_ascii=False, indent=2),
                    critique=critique,
                    suggestion=suggestion
                )
                
                # Log input
                self.db.create_agent_log(workflow_id, chapter_id, 'Agent D', f'Input (Item {idx})', input_data=prompt)
                
                try:
                    response = self.client.generate_text(prompt, provider_id=model_id)
                    active_model_id = self.client.get_active_model_id(model_id)
                    
                    # Log output
                    self.db.create_agent_log(workflow_id, chapter_id, 'Agent D', f'Output (Item {idx})', output_data=response, model_name=active_model_id)
                    
                    # Agent D returns a single JSON object
                    # We need to extract it carefully
                    import re
                    # Look for JSON object pattern
                    json_match = re.search(r'\{.*\}', response, re.DOTALL)
                    if json_match:
                        try:
                            refined_item = json.loads(json_match.group(0))
                            # Preserve type if missing
                            if 'type' not in refined_item and 'type' in original_item:
                                refined_item['type'] = original_item['type']
                            
                            # If original was QA/MCQ and refined lost options, try to keep them if not changed
                            if 'options' in original_item and 'options' not in refined_item:
                                refined_item['options'] = original_item['options']
                                
                            refined_items[idx] = refined_item
                        except json.JSONDecodeError:
                            print(f"Agent D failed to parse JSON for item {idx}")
                    else:
                        print(f"Agent D response did not contain JSON for item {idx}")
                        
                except Exception as e:
                    print(f"Agent D failed for item {idx}: {e}")
                    self.db.create_agent_log(workflow_id, chapter_id, 'Agent D', f'Error (Item {idx})', output_data=str(e))
                    
        return refined_items

    def run_workflow(self, content: str, count: int, item_type: str = 'qa', workflow_id: str = None, chapter_id: int = None, model_id: str = None) -> List[Dict[str, Any]]:
        """
        Run the full multi-agent workflow.
        """
        # Step 1: Analyze
        contexts = self.analyze_content(content, workflow_id, chapter_id, model_id)
        if not contexts:
            # Fallback: Create a dummy context with whole content
            contexts = [{
                "Topic": "General",
                "Key_Concepts": ["General Content"],
                "Source_Text": content[:2000] # Truncate
            }]
            
        # Step 2: Generate
        items = self.generate_initial_items(contexts, count, item_type, workflow_id, chapter_id, model_id)
        if not items:
            return []
            
        # Step 3: Review
        reviews = self.review_items(items, workflow_id, chapter_id, model_id)
        
        # Step 4: Refine
        final_items = self.refine_items(items, reviews, workflow_id, chapter_id, model_id)
        
        return final_items

# Global instance
multi_agent_generator = MultiAgentGenerator()
