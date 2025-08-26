# app/services/questionnaire.py
import yaml
from typing import Dict, List, Optional, Any, Union
from models.questionnaire import QuestionNode, Option
from services.nlp_analyzer import NLPAnalyzer # Import correct

class AdaptiveQuestionnaire:
    def __init__(self):
        self.questions = self._load_questions()
        self.responses = {} # Stocke les réponses {question_id: response_data}
        self.asked_questions = [] # Trace des questions posées
        self.current_path = [] # Chemin dynamique basé sur les réponses
        self.nlp_analyzer = NLPAnalyzer() # Instance de l'analyseur NLP

    def _load_questions(self) -> Dict[str, QuestionNode]:
        """Charge les questions depuis questions.yaml."""
        try:
            with open("data/questions.yaml", 'r', encoding='utf-8') as file:
                data = yaml.safe_load(file)
                questions_dict = {q_id: QuestionNode(**q_data) for q_id, q_data in data['questions'].items()}
                return questions_dict
        except FileNotFoundError:
            print("Fichier data/questions.yaml non trouvé.")
            return {}
        except yaml.YAMLError as e:
            print(f"Erreur de parsing YAML: {e}")
            return {}
        except Exception as e:
            print(f"Erreur lors du chargement des questions: {e}")
            return {}

    async def get_next_question(self, previous_response: Optional[Dict[str, Any]] = None) -> Optional[QuestionNode]:
        """Détermine la prochaine question basée sur les réponses précédentes."""
        if previous_response:
            question_id = previous_response.get('question_id')
            if not question_id:
                print("Erreur: 'question_id' manquant dans la réponse précédente.")
                return None

            self.responses[question_id] = previous_response
            self.asked_questions.append(question_id)

            current_question = self.questions.get(question_id)
            if not current_question:
                print(f"Erreur: Question '{question_id}' non trouvée.")
                return None

            # 1. Analyser le texte libre si nécessaire
            if current_question.type == 'text':
                answer_text = previous_response.get('answer', '')
                if isinstance(answer_text, str) and answer_text.strip():
                    nlp_analysis = await self.nlp_analyzer.analyze_free_text(answer_text)
                    previous_response['nlp_analysis'] = nlp_analysis # Ajouter l'analyse NLP à la réponse
                else:
                    previous_response['nlp_analysis'] = {} # Placeholder si pas de texte

            # 2. Logique adaptative basée sur la réponse
            # Vérifier les follow_up_conditions (ex: pain_location -> back -> back_pain_specific)
            # Pour body_map ou single/multiple choice
            if current_question.follow_up_conditions:
                answer_value = previous_response.get('answer')
                # Pour body_map, answer_value est une liste ou une chaîne
                if isinstance(answer_value, list):
                    # Vérifier chaque élément de la liste
                    for val in answer_value:
                        if isinstance(val, str) and val in current_question.follow_up_conditions:
                            next_q_id = current_question.follow_up_conditions[val]
                            if next_q_id and next_q_id in self.questions:
                                return self.questions[next_q_id]
                elif isinstance(answer_value, str) and answer_value in current_question.follow_up_conditions:
                    next_q_id = current_question.follow_up_conditions[answer_value]
                    if next_q_id and next_q_id in self.questions:
                        return self.questions[next_q_id]

            # Vérifier les follow_up basés sur les options choisies (multiple_choice, single_choice)
            # ou les follow_up par défaut de la question
            follow_up_questions_to_check = []

            # a. Vérifier les follow_up des options sélectionnées
            if current_question.type in ['multiple_choice', 'single_choice'] and current_question.options:
                selected_values = previous_response.get('answer', [])
                if not isinstance(selected_values, list):
                    selected_values = [selected_values] if selected_values else []

                for selected_val in selected_values:
                    # Trouver l'option correspondante
                    selected_option = next((opt for opt in current_question.options if hasattr(opt, 'value') and opt.value == selected_val), None)
                    if selected_option and hasattr(selected_option, 'follow_up') and selected_option.follow_up:
                        follow_up_questions_to_check.extend(selected_option.follow_up)

            # b. Ajouter les follow_up par défaut de la question courante
            if hasattr(current_question, 'follow_up') and current_question.follow_up:
                follow_up_questions_to_check.extend(current_question.follow_up)

            # c. Parcourir les questions follow_up potentielles
            for fq_id in follow_up_questions_to_check:
                if fq_id not in self.asked_questions and fq_id in self.questions:
                    self.current_path.append(fq_id) # Ajouter au chemin
                    return self.questions[fq_id]

        # Si c'est la première question ou si aucune logique adaptative ne s'applique,
        # retourner la première question non posée du fichier YAML
        if not self.asked_questions:
            # Retourner la première question du YAML
            if self.questions:
                # Parcourir les questions dans l'ordre du YAML
                for q_id in self.questions.keys():
                    if q_id not in self.asked_questions:
                        self.current_path.append(q_id)
                        return self.questions[q_id]
        else:
            # Si des questions ont été posées, essayer de continuer le chemin actuel
            # ou trouver la prochaine question non posée
            for q_id in self.questions.keys():
                 if q_id not in self.asked_questions:
                     self.current_path.append(q_id)
                     return self.questions[q_id]

        # Si toutes les questions potentielles ont été posées
        return None

    def get_responses(self) -> Dict[str, Any]:
        """Retourne toutes les réponses collectées."""
        return self.responses

    def reset(self):
        """Réinitialise le questionnaire."""
        self.responses = {}
        self.asked_questions = []
        self.current_path = []