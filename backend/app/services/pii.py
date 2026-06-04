import logging
import re
from typing import Dict, Tuple

logger = logging.getLogger(__name__)

# Try importing Presidio Analyzer
try:
    from presidio_analyzer import AnalyzerEngine
    from presidio_analyzer.nlp_engine import NlpEngineProvider
    HAS_PRESIDIO = True
except ImportError:
    HAS_PRESIDIO = False
    logger.warning("presidio-analyzer not installed. Using Regex fallback for PII sanitization.")

class PIISanitizer:
    def __init__(self):
        # Compiled regex patterns for fallback and supplementary use
        self.email_pattern = re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+')
        self.phone_pattern = re.compile(
            r'\+?\d{1,4}?[-.\s]?\(?\d{1,3}?\)?[-.\s]?'
            r'\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{1,9}'
        )
        
        # Heuristics for common names in greetings and sign-offs in emails
        self.name_patterns = [
            re.compile(r'(?:Hi|Hey|Dear|Hello|To:)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)'),
            re.compile(r'(?:Thanks|Best|Regards|Sincerely|From:),?\s*\n?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)')
        ]

        self.analyzer = None
        self.use_presidio = False

        if HAS_PRESIDIO:
            try:
                # Explicitly configure Presidio to use the lightweight en_core_web_sm model
                configuration = {
                    "nlp_engine_name": "spacy",
                    "models": [
                        {"lang_code": "en", "model_name": "en_core_web_sm"}
                    ],
                }
                provider = NlpEngineProvider(nlp_configuration=configuration)
                nlp_engine = provider.create_engine()
                self.analyzer = AnalyzerEngine(nlp_engine=nlp_engine)
                self.use_presidio = True
                logger.info(
                    "Microsoft Presidio Analyzer initialized successfully "
                    "with en_core_web_sm."
                )
            except Exception as e:
                logger.warning(
                    f"Failed to initialize Microsoft Presidio Analyzer engine: {e}. "
                    f"Falling back to Regex."
                )

    def mask_text(self, text: str) -> Tuple[str, Dict[str, str]]:
        """
        Mask sensitive data (Emails, Phone Numbers, Names) in the text.
        Returns the anonymized text and a mapping to restore original values.
        """
        if not text:
            return "", {}

        if not self.use_presidio:
            return self._mask_text_regex_fallback(text)

        try:
            # 1. Analyze using Microsoft Presidio for PERSON, EMAIL_ADDRESS, and PHONE_NUMBER
            results = self.analyzer.analyze(
                text=text,
                language='en',
                entities=["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER"]
            )

            # Convert to list of dicts for merge
            detections = []
            for res in results:
                detections.append({
                    "start": res.start,
                    "end": res.end,
                    "entity_type": res.entity_type
                })

            # 2. Supplement with Regex patterns to capture any missed items (hybrid approach)
            # Email regex
            for match in self.email_pattern.finditer(text):
                start, end = match.span()
                if not any(
                    d["start"] <= start < d["end"] or start <= d["start"] < end
                    for d in detections
                ):
                    detections.append({
                        "start": start,
                        "end": end,
                        "entity_type": "EMAIL_ADDRESS"
                    })

            # Phone regex
            for match in self.phone_pattern.finditer(text):
                phone_str = match.group(0).strip()
                if len(phone_str) > 7:
                    start, end = match.span()
                    if not any(
                        d["start"] <= start < d["end"] or start <= d["start"] < end
                        for d in detections
                    ):
                        detections.append({
                            "start": start,
                            "end": end,
                            "entity_type": "PHONE_NUMBER"
                        })

            # Name greeting/sign-off regex
            for name_regex in self.name_patterns:
                for match in name_regex.finditer(text):
                    name_str = match.group(1)
                    if name_str.lower() in [
                        "there", "all", "everyone", "team", "yesterday", "tomorrow"
                    ]:
                        continue
                    start, end = match.span(1)
                    if not any(
                        d["start"] <= start < d["end"] or start <= d["start"] < end
                        for d in detections
                    ):
                        detections.append({
                            "start": start,
                            "end": end,
                            "entity_type": "PERSON"
                        })

            # Sort results in reverse order of start index to safely replace in-place
            # without invalidating subsequent offsets.
            sorted_detections = sorted(detections, key=lambda x: x["start"], reverse=True)

            mapping = {}
            counter = {"EMAIL": 1, "PHONE": 1, "NAME": 1}
            masked_text = text

            # Map Presidio entities to our custom placeholders
            entity_map = {
                "EMAIL_ADDRESS": "EMAIL",
                "PHONE_NUMBER": "PHONE",
                "PERSON": "NAME"
            }

            # Map specific text value to existing placeholder to preserve consistency
            val_to_placeholder = {}

            for res in sorted_detections:
                val = text[res["start"]:res["end"]]
                local_type = entity_map.get(res["entity_type"])
                if not local_type:
                    continue

                if local_type == "NAME" and val.lower() in [
                    "there", "all", "everyone", "team", "yesterday", "tomorrow"
                ]:
                    continue

                if val in val_to_placeholder:
                    placeholder = val_to_placeholder[val]
                else:
                    placeholder = f"{{{{{local_type}_{counter[local_type]}}}}}"
                    val_to_placeholder[val] = placeholder
                    mapping[placeholder] = val
                    counter[local_type] += 1

                # Replace slice in masked_text
                masked_text = masked_text[:res["start"]] + placeholder + masked_text[res["end"]:]

            return masked_text, mapping

        except Exception as e:
            logger.error(f"Error during Presidio masking: {e}. Falling back to Regex.")
            return self._mask_text_regex_fallback(text)

    def _mask_text_regex_fallback(self, text: str) -> Tuple[str, Dict[str, str]]:
        mapping = {}
        counter = {"EMAIL": 1, "PHONE": 1, "NAME": 1}
        masked_text = text

        # 1. Mask Email addresses
        emails = self.email_pattern.findall(masked_text)
        for email in list(set(emails)):
            placeholder = f"{{{{EMAIL_{counter['EMAIL']}}}}}"
            mapping[placeholder] = email
            masked_text = masked_text.replace(email, placeholder)
            counter["EMAIL"] += 1

        # 2. Mask Phone numbers
        phones = [p.strip() for p in self.phone_pattern.findall(masked_text) if len(p.strip()) > 7]
        for phone in list(set(phones)):
            placeholder = f"{{{{PHONE_{counter['PHONE']}}}}}"
            mapping[placeholder] = phone
            masked_text = masked_text.replace(phone, placeholder)
            counter["PHONE"] += 1

        # 3. Mask Names (using context-aware greetings/sign-offs)
        for name_regex in self.name_patterns:
            matches = name_regex.findall(masked_text)
            for name in list(set(matches)):
                if name.lower() in ["there", "all", "everyone", "team"]:
                    continue
                placeholder = f"{{{{NAME_{counter['NAME']}}}}}"
                mapping[placeholder] = name
                masked_text = masked_text.replace(name, placeholder)
                counter["NAME"] += 1

        return masked_text, mapping

    def restore_text(self, masked_text: str, mapping: Dict[str, str]) -> str:
        """
        Restore the original sensitive data in a masked text using the mapping.
        """
        if not masked_text or not mapping:
            return masked_text

        restored_text = masked_text
        for placeholder, original in mapping.items():
            restored_text = restored_text.replace(placeholder, original)

        return restored_text

# Singleton instance
pii_sanitizer = PIISanitizer()
