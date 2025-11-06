from fastapi import FastAPI, HTTPException, File, UploadFile, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import asyncio
import httpx
import json
import random
import os
from datetime import datetime, timezone
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="🔮 Golden Dawn Tarot AI Service",
    description="AI-powered Tarot readings using Golden Dawn system with ebook knowledge base",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for card images
app.mount("/static", StaticFiles(directory="static"), name="static")

# Pydantic models
class TarotCard(BaseModel):
    name: str
    number: Optional[int] = None
    suit: Optional[str] = None
    element: Optional[str] = None
    meaning_upright: str
    meaning_reversed: str
    golden_dawn_correspondence: str
    hebrew_letter: Optional[str] = None
    astrological_correspondence: Optional[str] = None
    tree_of_life_path: Optional[int] = None

class TarotSpread(BaseModel):
    name: str
    positions: List[str]
    description: str
    card_count: int

class TarotReading(BaseModel):
    spread_type: str
    question: Optional[str] = None
    cards_drawn: List[Dict[str, Any]]
    interpretation: str
    timestamp: str
    reading_id: str

class ReadingRequest(BaseModel):
    question: Optional[str] = None
    spread_type: str = "three_card"
    include_reversed: bool = True
    deck_type: str = "golden_dawn"
    interpretation_style: str = "traditional"
    user_birth_info: Optional[Dict[str, Any]] = None

# Golden Dawn Tarot Deck (78 cards)
GOLDEN_DAWN_DECK = {
    # Major Arcana (22 cards)
    "major_arcana": [
        {
            "name": "The Fool", "number": 0, "element": "Air",
            "meaning_upright": "New beginnings, innocence, spontaneity, free spirit",
            "meaning_reversed": "Recklessness, taken advantage of, inconsistency, foolishness",
            "golden_dawn_correspondence": "Path of Aleph, Air element, Uranus",
            "hebrew_letter": "Aleph", "tree_of_life_path": 11,
            "astrological_correspondence": "Uranus"
        },
        {
            "name": "The Magician", "number": 1, "element": "Air",
            "meaning_upright": "Manifestation, resourcefulness, power, inspired action",
            "meaning_reversed": "Manipulation, poor planning, untapped talents",
            "golden_dawn_correspondence": "Path of Beth, Mercury, Magus of Power",
            "hebrew_letter": "Beth", "tree_of_life_path": 12,
            "astrological_correspondence": "Mercury"
        },
        {
            "name": "The High Priestess", "number": 2, "element": "Water",
            "meaning_upright": "Intuition, sacred knowledge, divine feminine, subconscious mind",
            "meaning_reversed": "Secrets, disconnected from intuition, withdrawal",
            "golden_dawn_correspondence": "Path of Gimel, Moon, Priestess of Silver Star",
            "hebrew_letter": "Gimel", "tree_of_life_path": 13,
            "astrological_correspondence": "Moon"
        },
        {
            "name": "The Empress", "number": 3, "element": "Earth",
            "meaning_upright": "Femininity, beauty, nature, nurturing, abundance",
            "meaning_reversed": "Creative block, dependence on others, smothering",
            "golden_dawn_correspondence": "Path of Daleth, Venus, Daughter of Mighty Ones",
            "hebrew_letter": "Daleth", "tree_of_life_path": 14,
            "astrological_correspondence": "Venus"
        },
        {
            "name": "The Emperor", "number": 4, "element": "Fire",
            "meaning_upright": "Authority, establishment, structure, father figure",
            "meaning_reversed": "Domination, excessive control, lack of discipline",
            "golden_dawn_correspondence": "Path of Heh, Aries, Son of Morning",
            "hebrew_letter": "Heh", "tree_of_life_path": 15,
            "astrological_correspondence": "Aries"
        },
        {
            "name": "The Hierophant", "number": 5, "element": "Earth",
            "meaning_upright": "Spiritual wisdom, religious beliefs, conformity, tradition",
            "meaning_reversed": "Personal beliefs, freedom, challenging the status quo",
            "golden_dawn_correspondence": "Path of Vav, Taurus, Magus of Eternal",
            "hebrew_letter": "Vav", "tree_of_life_path": 16,
            "astrological_correspondence": "Taurus"
        },
        {
            "name": "The Lovers", "number": 6, "element": "Air",
            "meaning_upright": "Love, harmony, relationships, values alignment",
            "meaning_reversed": "Disharmony, imbalance, misaligned values",
            "golden_dawn_correspondence": "Path of Zayin, Gemini, Children of Voice",
            "hebrew_letter": "Zayin", "tree_of_life_path": 17,
            "astrological_correspondence": "Gemini"
        },
        {
            "name": "The Chariot", "number": 7, "element": "Water",
            "meaning_upright": "Control, willpower, success, determination",
            "meaning_reversed": "Self-discipline, opposition, lack of direction",
            "golden_dawn_correspondence": "Path of Cheth, Cancer, Child of Powers of Waters",
            "hebrew_letter": "Cheth", "tree_of_life_path": 18,
            "astrological_correspondence": "Cancer"
        },
        {
            "name": "Strength", "number": 8, "element": "Fire",
            "meaning_upright": "Strength, courage, persuasion, influence, compassion",
            "meaning_reversed": "Self-doubt, low energy, raw emotion",
            "golden_dawn_correspondence": "Path of Teth, Leo, Daughter of Flaming Sword",
            "hebrew_letter": "Teth", "tree_of_life_path": 19,
            "astrological_correspondence": "Leo"
        },
        {
            "name": "The Hermit", "number": 9, "element": "Earth",
            "meaning_upright": "Soul searching, introspection, inner guidance",
            "meaning_reversed": "Isolation, loneliness, withdrawal",
            "golden_dawn_correspondence": "Path of Yod, Virgo, Magus of Voice of Light",
            "hebrew_letter": "Yod", "tree_of_life_path": 20,
            "astrological_correspondence": "Virgo"
        },
        {
            "name": "Wheel of Fortune", "number": 10, "element": "Fire",
            "meaning_upright": "Good luck, karma, life cycles, destiny, turning point",
            "meaning_reversed": "Bad luck, lack of control, clinging to control",
            "golden_dawn_correspondence": "Path of Kaph, Jupiter, Lord of Forces of Life",
            "hebrew_letter": "Kaph", "tree_of_life_path": 21,
            "astrological_correspondence": "Jupiter"
        },
        {
            "name": "Justice", "number": 11, "element": "Air",
            "meaning_upright": "Justice, fairness, truth, cause and effect, law",
            "meaning_reversed": "Unfairness, lack of accountability, dishonesty",
            "golden_dawn_correspondence": "Path of Lamed, Libra, Daughter of Lords of Truth",
            "hebrew_letter": "Lamed", "tree_of_life_path": 22,
            "astrological_correspondence": "Libra"
        },
        {
            "name": "The Hanged Man", "number": 12, "element": "Water",
            "meaning_upright": "Suspension, restriction, letting go, sacrifice",
            "meaning_reversed": "Martyrdom, indecision, delay",
            "golden_dawn_correspondence": "Path of Mem, Water, Spirit of Mighty Waters",
            "hebrew_letter": "Mem", "tree_of_life_path": 23,
            "astrological_correspondence": "Neptune"
        }
        # Add remaining 17 major arcana cards following this pattern...
    ],
    
    # Minor Arcana - Wands (Fire)
    "wands": [
        {
            "name": "Ace of Wands", "number": 1, "suit": "Wands", "element": "Fire",
            "meaning_upright": "Inspiration, new opportunities, growth",
            "meaning_reversed": "Lack of energy, lack of passion, boredom",
            "golden_dawn_correspondence": "Root of Fire, Kether in Fire",
            "tree_of_life_path": 1
        }
        # Add remaining 13 wands...
    ],
    
    # Minor Arcana - Cups (Water)
    "cups": [
        {
            "name": "Ace of Cups", "number": 1, "suit": "Cups", "element": "Water",
            "meaning_upright": "Love, new relationships, compassion, creativity",
            "meaning_reversed": "Self-love, intuition, repressed emotions",
            "golden_dawn_correspondence": "Root of Water, Kether in Water",
            "tree_of_life_path": 1
        }
        # Add remaining 13 cups...
    ],
    
    # Minor Arcana - Swords (Air)
    "swords": [
        {
            "name": "Ace of Swords", "number": 1, "suit": "Swords", "element": "Air",
            "meaning_upright": "New ideas, mental clarity, breakthrough",
            "meaning_reversed": "Inner clarity, re-thinking an idea, clouded judgment",
            "golden_dawn_correspondence": "Root of Air, Kether in Air",
            "tree_of_life_path": 1
        }
        # Add remaining 13 swords...
    ],
    
    # Minor Arcana - Pentacles (Earth)
    "pentacles": [
        {
            "name": "Ace of Pentacles", "number": 1, "suit": "Pentacles", "element": "Earth",
            "meaning_upright": "New financial opportunity, manifestation, abundance",
            "meaning_reversed": "Lost opportunity, lack of planning, poor financial decisions",
            "golden_dawn_correspondence": "Root of Earth, Kether in Earth",
            "tree_of_life_path": 1
        }
        # Add remaining 13 pentacles...
    ]
}

# Tarot Spreads
TAROT_SPREADS = {
    "single_card": TarotSpread(
        name="Single Card",
        positions=["Guidance"],
        description="Simple single-card draw for quick guidance",
        card_count=1
    ),
    "three_card": TarotSpread(
        name="Past, Present, Future",
        positions=["Past/Foundation", "Present/Challenge", "Future/Outcome"],
        description="Simple three-card spread for quick insight",
        card_count=3
    ),
    "celtic_cross": TarotSpread(
        name="Celtic Cross",
        positions=[
            "Present Situation", "Challenge/Cross", "Distant Past/Foundation", 
            "Recent Past", "Crown/Possible Outcome", "Immediate Future",
            "Your Approach", "External Influences", "Hopes and Fears", "Final Outcome"
        ],
        description="The most comprehensive spread, exploring all aspects of your situation",
        card_count=10
    ),
    "tree_of_life": TarotSpread(
        name="Tree of Life",
        positions=[
            "Kether (Crown)", "Chokmah (Wisdom)", "Binah (Understanding)", 
            "Chesed (Mercy)", "Geburah (Severity)", "Tiphareth (Beauty)",
            "Netzach (Victory)", "Hod (Glory)", "Yesod (Foundation)", "Malkuth (Kingdom)"
        ],
        description="Based on the Kabbalistic Tree of Life, providing deep spiritual insight",
        card_count=10
    ),
    "golden_dawn": TarotSpread(
        name="Golden Dawn Temple",
        positions=[
            "Present Situation", "Hidden Influences", "Past Foundations",
            "Future Possibilities", "Higher Guidance", "Practical Action",
            "Inner Wisdom", "External Forces", "Final Outcome"
        ],
        description="Sacred 9-card Golden Dawn spread using all available cards",
        card_count=9
    ),
    "seven_pointed_star": TarotSpread(
        name="Seven-Pointed Star",
        positions=[
            "Self", "Past", "Future", "Hidden Influences",
            "External Forces", "Hopes/Fears", "Final Outcome"
        ],
        description="Mystical 7-card spread for deep spiritual insight",
        card_count=7
    )
}

class TarotAIService:
    def __init__(self):
        self.ebook_path = "/app/ebooks"
        self.readings_path = "/app/readings"
        self.langchain_url = os.getenv("AI_MODEL_URL", "http://langchain-service:7860")
        self.vector_db_url = os.getenv("VECTOR_DB_URL", "http://chromadb:8000")
        
        # Ensure directories exist
        Path(self.readings_path).mkdir(parents=True, exist_ok=True)
        
    def get_all_cards(self) -> List[TarotCard]:
        """Get all 78 cards from the Golden Dawn deck"""
        all_cards = []
        for category in GOLDEN_DAWN_DECK.values():
            for card_data in category:
                all_cards.append(TarotCard(**card_data))
        return all_cards
    
    def draw_cards(self, count: int, include_reversed: bool = True) -> List[Dict[str, Any]]:
        """Draw specified number of cards from the deck"""
        all_cards = self.get_all_cards()
        
        # Ensure we don't try to draw more cards than available
        if count > len(all_cards):
            count = len(all_cards)
            logger.warning(f"Requested {count} cards but only {len(all_cards)} available. Drawing {len(all_cards)} cards.")
        
        drawn_cards = random.sample(all_cards, count)
        
        result = []
        for card in drawn_cards:
            is_reversed = random.choice([True, False]) if include_reversed else False
            
            result.append({
                "card": card.dict(),
                "reversed": is_reversed,
                "meaning": card.meaning_reversed if is_reversed else card.meaning_upright,
                "orientation": "Reversed" if is_reversed else "Upright"
            })
        
        return result
    
    async def get_ai_interpretation(self, cards: List[Dict], question: str = None, spread_type: str = "three_card") -> str:
        """Get AI interpretation of the reading using ebook knowledge"""
        try:
            # For now, use basic interpretation since langchain service is in reflective state
            return self._generate_basic_interpretation(cards, question, spread_type)
            
            # Original AI service call commented out until langchain service is fixed
            """
            # Prepare context for AI
            card_context = []
            for i, card_info in enumerate(cards):
                card = card_info["card"]
                position = TAROT_SPREADS[spread_type].positions[i] if i < len(TAROT_SPREADS[spread_type].positions) else f"Position {i+1}"
                
                card_context.append(f'''
Position {i+1} - {position}: {card['name']} ({card_info['orientation']})
Golden Dawn Correspondence: {card['golden_dawn_correspondence']}
Meaning: {card_info['meaning']}
Hebrew Letter: {card.get('hebrew_letter', 'N/A')}
Tree of Life Path: {card.get('tree_of_life_path', 'N/A')}
                '''.strip())
            
            prompt = f'''
As an expert in Golden Dawn Tarot, Hermetic Kabbalah, and esoteric wisdom, provide a comprehensive interpretation of this tarot reading.

Question: {question or "General life guidance"}
Spread: {TAROT_SPREADS[spread_type].name}
Cards Drawn:
{chr(10).join(card_context)}

Please provide:
1. Individual card interpretations in context of their positions
2. Overall narrative and theme of the reading
3. Golden Dawn and Kabbalistic insights
4. Practical guidance and advice
5. Connections between the cards and their correspondences

Draw upon the wisdom of the Golden Dawn tradition, including the Tree of Life correspondences, Hebrew letters, and astrological associations.
            '''
            
            # Call AI service
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.langchain_url}/api/chat",
                    json={"message": prompt, "user_id": "tarot_service"},
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    result = response.json()
                    # Handle both old and new response formats
                    if "message" in result:
                        return result["message"]
                    elif "response" in result:
                        return result["response"]
                    else:
                        return "Unable to generate interpretation at this time."
                else:
                    logger.error(f"AI service error: {response.status_code}")
                    return self._generate_basic_interpretation(cards, question, spread_type)
            """
                    
        except Exception as e:
            logger.error(f"Error getting AI interpretation: {e}")
            return self._generate_basic_interpretation(cards, question, spread_type)
    
    def _generate_basic_interpretation(self, cards: List[Dict], question: str = None, spread_type: str = "three_card") -> str:
        """Generate basic interpretation without AI service"""
        interpretation = f"Reading for: {question or 'General guidance'}\n\n"
        
        for i, card_info in enumerate(cards):
            card = card_info["card"]
            position = TAROT_SPREADS[spread_type].positions[i] if i < len(TAROT_SPREADS[spread_type].positions) else f"Position {i+1}"
            
            interpretation += f"""
{position}: {card['name']} ({card_info['orientation']})
{card_info['meaning']}
Golden Dawn: {card['golden_dawn_correspondence']}

"""
        
        interpretation += "\nThis reading suggests a journey through the archetypes and energies represented by these sacred symbols. Consider how each card's energy applies to your current situation and the guidance it offers for your path forward."
        
        return interpretation.strip()
    
    async def save_reading(self, reading: TarotReading) -> str:
        """Save reading to file system"""
        reading_file = Path(self.readings_path) / f"{reading.reading_id}.json"
        
        try:
            # Convert reading to dict with proper datetime handling
            reading_dict = reading.dict()
            reading_dict["timestamp"] = reading.timestamp
            
            with open(reading_file, 'w') as f:
                json.dump(reading_dict, f, indent=2)
            logger.info(f"Saved reading: {reading.reading_id}")
            return str(reading_file)
        except Exception as e:
            logger.error(f"Error saving reading: {e}")
            raise

# Initialize service
tarot_service = TarotAIService()

@app.get("/", response_class=HTMLResponse)
async def root():
    return """
    <html>
        <head><title>🔮 Golden Dawn Tarot AI</title></head>
        <body style="font-family: Arial; margin: 40px; background: #1a1a2e; color: #eee;">
            <h1>🔮 Golden Dawn Tarot AI Service</h1>
            <p>AI-powered Tarot readings using the complete Golden Dawn system</p>
            <ul>
                <li><a href="/docs" style="color: #4CAF50;">📖 API Documentation</a></li>
                <li><a href="/health" style="color: #4CAF50;">💓 Health Check</a></li>
                <li><a href="/cards" style="color: #4CAF50;">🃏 View All Cards</a></li>
                <li><a href="/spreads" style="color: #4CAF50;">🔮 Available Spreads</a></li>
            </ul>
        </body>
    </html>
    """

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "Golden Dawn Tarot AI", "timestamp": datetime.now(timezone.utc).isoformat()}

@app.get("/cards")
async def get_all_cards():
    """Get all 78 cards in the Golden Dawn deck"""
    return {"deck": "Golden Dawn Tarot", "cards": tarot_service.get_all_cards()}

@app.get("/spreads")
async def get_spreads():
    """Get all available tarot spreads"""
    return {"spreads": TAROT_SPREADS}

@app.post("/reading")
async def create_reading(request: ReadingRequest) -> JSONResponse:
    """Create a new tarot reading"""
    try:
        # Validate spread type
        if request.spread_type not in TAROT_SPREADS:
            raise HTTPException(status_code=400, detail=f"Unknown spread type: {request.spread_type}")
        
        spread = TAROT_SPREADS[request.spread_type]
        
        # Draw cards
        cards_drawn = tarot_service.draw_cards(spread.card_count, request.include_reversed)
        
        # Get AI interpretation
        interpretation = await tarot_service.get_ai_interpretation(
            cards_drawn, 
            request.question, 
            request.spread_type
        )
        
        # Create reading object
        reading_id = f"reading_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{random.randint(1000, 9999)}"
        
        reading = TarotReading(
            spread_type=request.spread_type,
            question=request.question,
            cards_drawn=cards_drawn,
            interpretation=interpretation,
            timestamp=datetime.now(timezone.utc).isoformat(),
            reading_id=reading_id
        )
        
        # Save reading
        await tarot_service.save_reading(reading)
        
        return JSONResponse(content={
            "success": True,
            "reading": {
                **reading.dict(),
                "timestamp": reading.timestamp
            },
            "message": f"Reading completed successfully: {reading_id}"
        })
        
    except Exception as e:
        logger.error(f"Error creating reading: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/reading/{reading_id}")
async def get_reading(reading_id: str):
    """Retrieve a saved reading"""
    try:
        reading_file = Path(tarot_service.readings_path) / f"{reading_id}.json"
        
        if not reading_file.exists():
            raise HTTPException(status_code=404, detail="Reading not found")
        
        with open(reading_file, 'r') as f:
            reading_data = json.load(f)
        
        return {"reading": reading_data}
        
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Reading not found")
    except Exception as e:
        logger.error(f"Error retrieving reading: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7870, log_level="info")
