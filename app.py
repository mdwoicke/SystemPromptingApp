import os
import re
import json
import logging
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
import requests
import trafilatura
from sqlalchemy.dialects.postgresql import JSONB

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev")

# Database configuration with enhanced connection settings
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,           # Enable connection pre-ping
    "pool_recycle": 300,             # Recycle connections every 5 minutes
    "pool_timeout": 30,              # Connection timeout of 30 seconds
    "max_overflow": 10,              # Allow up to 10 connections over pool size
    "pool_size": 5,                  # Maintain a pool of 5 connections
    "connect_args": {
        "connect_timeout": 10,        # PostgreSQL connection timeout
        "keepalives": 1,             # Enable keepalive
        "keepalives_idle": 30,       # Idle time before sending keepalive
        "keepalives_interval": 10,    # Interval between keepalives
        "keepalives_count": 5        # Number of keepalive attempts
    }
}

# Initialize extensions
db = SQLAlchemy(app)
csrf = CSRFProtect(app)

# Add more detailed logging for database operations
def init_db_logging():
    logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
    logging.getLogger('sqlalchemy.pool').setLevel(logging.DEBUG)

init_db_logging()

class Message(db.Model):
    __tablename__ = 'system_message'  # Match the table name from models.py
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    bio = db.Column(db.Text, nullable=False)
    voice_style = db.Column(db.Text, nullable=False)
    persona = db.Column(JSONB, nullable=False)
    rules = db.Column(JSONB, nullable=False)
    instructions = db.Column(JSONB, nullable=False)
    example_dialogue = db.Column(JSONB, nullable=False)
    published = db.Column(db.Boolean, default=False)
    published_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    original_id = db.Column(db.Integer, db.ForeignKey('system_message.id'), nullable=True)
    version_number = db.Column(db.Integer, default=1)
    version_note = db.Column(db.Text)

    # Add relationship for version tracking
    copies = db.relationship(
        'Message',
        backref=db.backref('original', remote_side=[id]),
        foreign_keys=[original_id]
    )

    def to_dict(self):
        """Convert message to dictionary format"""
        return {
            'id': self.id,
            'name': self.name,
            'bio': self.bio,
            'voice_style': self.voice_style,
            'persona': self.persona,
            'rules': self.rules,
            'instructions': self.instructions,
            'example_dialogue': self.example_dialogue,
            'published': self.published,
            'published_at': self.published_at.isoformat() if self.published_at else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'original_id': self.original_id,
            'version_number': self.version_number,
            'version_note': self.version_note
        }

    def get_version_history(self):
        """Get the complete version history of this message"""
        if self.original_id:
            # This is a copy, start from the original
            original = Message.query.get(self.original_id)
            if original:
                return original.get_version_history()
            return [self]  # Original not found, return just this message
        else:
            # This is an original, get all copies
            versions = [self]
            for copy in self.copies:
                versions.append(copy)
            return sorted(versions, key=lambda x: x.version_number)

# Create all database tables
with app.app_context():
    db.create_all()
    logger.info("Database tables created successfully")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/messages')
def list_messages():
    try:
        messages = Message.query.order_by(Message.created_at.desc()).all()
        logger.debug(f"Found {len(messages)} messages")
        for msg in messages:
            logger.debug(f"Message ID: {msg.id}, Name: {msg.name}")
        return render_template('list.html', messages=messages)
    except Exception as e:
        logger.error(f"Error fetching messages: {e}", exc_info=True)
        flash('Error loading messages', 'error')
        return render_template('list.html', messages=[])

@app.route('/messages/<int:id>/delete', methods=['GET', 'POST'])
def delete_message(id):
    message = Message.query.get_or_404(id)
    try:
        db.session.delete(message)
        db.session.commit()
        flash('Message deleted successfully', 'success')
    except Exception as e:
        logger.error(f"Error deleting message: {e}")
        db.session.rollback()
        flash('Error deleting message', 'error')
    return redirect(url_for('list_messages'))

@app.route('/generate-template')
def generate_template():
    return render_template('generate.html')

@app.route('/messages/<int:id>')
def preview_message(id):
    message = Message.query.get_or_404(id)
    return render_template('preview.html', message=message)

@app.route('/optimize')
def optimize_view():
    """Route for the schema optimization interface"""
    messages = Message.query.order_by(Message.created_at.desc()).all()
    return render_template('optimize.html', messages=messages)

@app.route('/optimize-schema/<int:id>', methods=['POST'])
def optimize_schema(id):
    try:
        message = Message.query.get_or_404(id)
        data = request.get_json()
        custom_request = data.get('custom_optimization', '') if data else ''

        if not custom_request:
            return jsonify({'error': 'No optimization request provided'}), 400

        # Log optimization request
        logger.info(f"Optimization request received for template {id}: {custom_request}")

        # Construct optimization prompt
        prompt = f"""Analyze and modify this template based on the following request:
{custom_request}

Current Template:
Bio: {message.bio}
Voice Style: {message.voice_style}
Persona: {json.dumps(message.persona, indent=2)}
Rules: {json.dumps(message.rules, indent=2)}
Instructions: {json.dumps(message.instructions, indent=2)}
Example Dialogue: {json.dumps(message.example_dialogue, indent=2)}

Return a JSON object containing ONLY the fields that need to be updated:
{{
    "rules": ["list of all rules including any new ones"],
    "bio": "only if it needs updating",
    "voice_style": "only if it needs updating",
    "persona": {{}},
    "instructions": [],
    "example_dialogue": []
}}

Important:
- Return valid JSON only
- For rules, include ALL existing rules plus any new ones
- Only include fields that actually need updating
- Keep existing content for fields not mentioned in request"""

        # Call Perplexity API
        headers = {
            'Authorization': f'Bearer {os.environ["PERPLEXITY_API_KEY"]}',
            'Content-Type': 'application/json'
        }

        logger.debug("Sending request to Perplexity API")
        api_response = requests.post(
            'https://api.perplexity.ai/chat/completions',
            headers=headers,
            json={
                'model': 'llama-3.1-sonar-small-128k-online',
                'messages': [
                    {'role': 'system', 'content': 'You are an expert in optimizing message templates. Return only valid JSON with the exact fields that need updating. You can add new rules, modify dialogue, or update any part of the template.'},
                    {'role': 'user', 'content': prompt}
                ],
                'temperature': 0.2
            },
            timeout=30
        )

        if not api_response.ok:
            logger.error(f"API Error: {api_response.text}")
            return jsonify({'error': 'Failed to optimize template'}), api_response.status_code

        response_data = api_response.json()
        logger.debug(f"API Response received: {response_data}")

        if not response_data.get('choices'):
            logger.error("No choices in API response")
            return jsonify({'error': 'Invalid API response'}), 500

        # Extract JSON from the response
        content = response_data['choices'][0]['message']['content']
        logger.debug(f"Raw content from API: {content}")

        try:
            # First try to parse the content directly
            updates = json.loads(content)
            if not isinstance(updates, dict):
                logger.error(f"Invalid updates format: {type(updates)}")
                return jsonify({'error': 'Invalid update format received'}), 500

            # Apply updates to the message
            if 'rules' in updates:
                message.rules = updates['rules']
            if 'bio' in updates:
                message.bio = updates['bio']
            if 'voice_style' in updates:
                message.voice_style = updates['voice_style']
            if 'persona' in updates:
                message.persona = updates['persona']
            if 'instructions' in updates:
                message.instructions = updates['instructions']
            if 'example_dialogue' in updates:
                message.example_dialogue = updates['example_dialogue']

            message.updated_at = datetime.utcnow()
            db.session.commit()
            return jsonify({'success': True})

        except json.JSONDecodeError as e:
            logger.error(f"JSON Parse Error: {e}")
            # Try to find JSON object in the content
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                try:
                    updates = json.loads(json_match.group())
                    if isinstance(updates, dict):
                        # Apply updates
                        if 'rules' in updates:
                            message.rules = updates['rules']
                        if 'bio' in updates:
                            message.bio = updates['bio']
                        if 'voice_style' in updates:
                            message.voice_style = updates['voice_style']
                        if 'persona' in updates:
                            message.persona = updates['persona']
                        if 'instructions' in updates:
                            message.instructions = updates['instructions']
                        if 'example_dialogue' in updates:
                            message.example_dialogue = updates['example_dialogue']

                        message.updated_at = datetime.utcnow()
                        db.session.commit()
                        return jsonify({'success': True})
                except Exception as e:
                    logger.error(f"Failed to parse or apply updates: {e}", exc_info=True)
            return jsonify({'error': 'Failed to parse optimization updates'}), 500

    except Exception as e:
        logger.error(f"Unexpected error in optimize_schema: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/get-template/<int:id>')
def get_template(id):
    """Route to get template details"""
    try:
        message = Message.query.get_or_404(id)
        return jsonify({
            'bio': message.bio,
            'voice_style': message.voice_style,
            'persona': message.persona,
            'rules': message.rules,
            'instructions': message.instructions,
            'example_dialogue': message.example_dialogue
        })
    except Exception as e:
        logger.error(f"Error getting template: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/update-template/<int:id>', methods=['POST'])
def update_template(id):
    """Route to update template with edited values"""
    try:
        message = Message.query.get_or_404(id)
        data = request.get_json()

        if not data:
            return jsonify({'error': 'No update data provided'}), 400

        # Update basic fields
        if 'bio' in data:
            message.bio = data['bio']
        if 'voice_style' in data:
            message.voice_style = data['voice_style']

        # Update persona
        if 'persona' in data:
            # Merge with existing persona to preserve other fields
            updated_persona = message.persona.copy() if message.persona else {}
            updated_persona.update(data['persona'])
            message.persona = updated_persona

        # Update array fields
        if 'rules' in data:
            message.rules = data['rules']
        if 'instructions' in data:
            message.instructions = data['instructions']
        if 'example_dialogue' in data:
            message.example_dialogue = data['example_dialogue']

        message.updated_at = datetime.utcnow()
        db.session.commit()

        return jsonify({'success': True, 'message': 'Template updated successfully'})

    except Exception as e:
        logger.error(f"Error updating template: {e}", exc_info=True)
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/apply-optimization/<int:id>', methods=['POST'])
def apply_optimization(id):
    """Route to apply optimizations to a template"""
    try:
        message = Message.query.get_or_404(id)
        data = request.get_json()
        custom_request = data.get('custom_optimization', '') if data else ''

        if custom_request:
            # Use Perplexity API to process the custom request
            headers = {
                'Authorization': f'Bearer {os.environ["PERPLEXITY_API_KEY"]}',
                'Content-Type': 'application/json'
            }

            prompt = f"""Apply the following optimization request to this template:
Custom Request: {custom_request}

Current Template:
Bio: {message.bio}
Voice Style: {message.voice_style}
Persona: {json.dumps(message.persona, indent=2)}
Rules: {json.dumps(message.rules, indent=2)}
Instructions: {json.dumps(message.instructions, indent=2)}
Example Dialogue: {json.dumps(message.example_dialogue, indent=2)}

Based on the custom request, return a JSON object with ONLY the fields that need to be updated:
{{
    "rules": ["list of all rules including any new ones"],
    "bio": "only if it needs updating",
    "voice_style": "only if it needs updating",
    "persona": {{}},
    "instructions": [],
    "example_dialogue": []
}}

Important:
- Return valid JSON only
- Include ALL existing rules plus any new ones in the rules array
- Only include fields that actually need updating
- Keep existing content for fields not mentioned in custom request"""

            logger.debug("Sending optimization request to Perplexity API")
            api_response = requests.post(
                'https://api.perplexity.ai/chat/completions',
                headers=headers,
                json={
                    'model': 'llama-3.1-sonar-small-128k-online',
                    'messages': [
                        {'role': 'system', 'content': 'You are an expert in optimizing message templates. Return only valid JSON with the exact fields that need updating. You can add new rules, modify dialogue, or update any part of the template.'},
                        {'role': 'user', 'content': prompt}
                    ],
                    'temperature': 0.2
                },
                timeout=30
            )

            if not api_response.ok:
                logger.error(f"API Error: {api_response.text}")
                return jsonify({'error': 'Failed to apply optimization'}), 500

            response_data = api_response.json()
            content = response_data['choices'][0]['message']['content']

            # Extract JSON from the response
            content = response_data['choices'][0]['message']['content']
            logger.debug(f"Raw content from API: {content}")

            # First try to parse the content directly
            try:
                updates = json.loads(content)
                logger.debug(f"Parsed updates: {updates}")

                # Apply updates to the message
                if isinstance(updates, dict):
                    if 'rules' in updates:
                        message.rules = updates['rules']
                    if 'bio' in updates:
                        message.bio = updates['bio']
                    if 'voice_style' in updates:
                        message.voice_style = updates['voice_style']
                    if 'persona' in updates:
                        message.persona = updates['persona']
                    if 'instructions' in updates:
                        message.instructions = updates['instructions']
                    if 'example_dialogue' in updates:
                        message.example_dialogue = updates['example_dialogue']

                    message.updated_at = datetime.utcnow()
                    db.session.commit()
                    return jsonify({'success': True, 'message': 'Template updated successfully'})

            except json.JSONDecodeError as e:
                logger.error(f"JSON Parse Error: {e}")
                # If direct parsing fails, try to extract JSON object
                json_match = re.search(r'\{[\s\S]*\}', content)
                if json_match:
                    try:
                        updates = json.loads(json_match.group())
                        if isinstance(updates, dict):
                            # Apply the same updates as above
                            if 'rules' in updates:
                                message.rules = updates['rules']
                            if 'bio' in updates:
                                message.bio = updates['bio']
                            if 'voice_style' in updates:
                                message.voice_style = updates['voice_style']
                            if 'persona' in updates:
                                message.persona = updates['persona']
                            if 'instructions' in updates:
                                message.instructions = updates['instructions']
                            if 'example_dialogue' in updates:
                                message.example_dialogue = updates['example_dialogue']

                            message.updated_at = datetime.utcnow()
                            db.session.commit()
                            return jsonify({'success': True, 'message': 'Template updated successfully'})
                    except Exception as e:
                        logger.error(f"Failed to parse or apply updates: {e}", exc_info=True)

            return jsonify({'error': 'Failed to optimize schema'}), 500

        return jsonify({
            'success': True, 
            'template_id': message.id,
            'message': 'Template updated successfully'
        })

    except Exception as e:
        logger.error(f"Error applying optimizations: {e}", exc_info=True)
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/builder')
def template_builder():
    """Route for the template builder interface"""
    return render_template('builder.html')

@app.route('/list_categories')
def list_categories():
    """Route for listing categories"""
    return render_template('categories.html')

@app.route('/list_tags')
def list_tags():
    """Route for listing tags"""
    return render_template('tags.html')

@app.route('/generate-schema', methods=['POST'])
def generate_schema():
    """Route to generate a new schema using Perplexity API"""
    try:
        data = request.get_json()
        prompt = data.get('prompt')
        url = data.get('url', '')

        if not prompt:
            return jsonify({'error': 'Prompt is required'}), 400

        # If URL is provided, get website content
        context = ""
        if url:
            try:
                downloaded = trafilatura.fetch_url(url)
                context = trafilatura.extract(downloaded)
                if context:
                    prompt = f"Based on this website content:\n{context}\n\n{prompt}"
            except Exception as e:
                logger.warning(f"Failed to fetch URL content: {e}")

        # Call Perplexity API
        headers = {
            'Authorization': f'Bearer {os.environ["PERPLEXITY_API_KEY"]}',
            'Content-Type': 'application/json'
        }

        api_response = requests.post(
            'https://api.perplexity.ai/chat/completions',
            headers=headers,
            json={
                'model': 'llama-3.1-sonar-small-128k-online',
                'messages': [
                    {'role': 'system', 'content': 'You are an expert in creating system message templates. Return only valid JSON in this format: {"bio": "...", "voice_style": "...", "persona": {...}, "rules": ["Please provide your contact information", "Customize your order"], "instructions": ["Create an account by providing your contact information", "Browse the menu and select items", "Customize your order with preferences", "Submit your order through the app", "Track your order status in real-time"], "example_dialogue": ["Agent: Hello! How can I help you today?", "Customer: I would like to place an order.", "Agent: I\'d be happy to help you with that!", "Customer: Thank you."]}'},
                    {'role': 'user', 'content': prompt}
                ],
                'temperature': 0.2
            }
        )

        if not api_response.ok:
            logger.error(f"API Error: {api_response.text}")
            return jsonify({'error': 'Failed to generate schema'}), 500

        response_data = api_response.json()
        if not response_data.get('choices'):
            return jsonify({'error': 'Invalid API response'}), 500

        # Extract JSON from the response
        try:
            content = response_data['choices'][0]['message']['content']
            try:
                # First try to parse content directly
                schema_data = json.loads(content)
            except json.JSONDecodeError:
                # If that fails, try to find JSON object in the content
                json_match = re.search(r'\{[\s\S]*\}', content)
                if not json_match:
                    return jsonify({'error': 'Invalid schema format'}), 500
                try:
                    schema_data = json.loads(json_match.group())
                except json.JSONDecodeError:
                    return jsonify({'error': 'Invalid schema format'}), 500

            # Validate required fields
            required_fields = ['bio', 'voice_style', 'persona', 'rules', 'instructions', 'example_dialogue']
            if not all(field in schema_data for field in required_fields):
                return jsonify({'error': 'Missing required fields'}), 500

            # Ensure rules and instructions are lists
            if isinstance(schema_data.get('rules'), str):
                schema_data['rules'] = [schema_data['rules']]
            if isinstance(schema_data.get('instructions'), str):
                schema_data['instructions'] = [schema_data['instructions']]

            # Ensure example_dialogue is a list of strings
            if isinstance(schema_data.get('example_dialogue'), dict):
                dialogue = []
                for speaker, text in schema_data['example_dialogue'].items():
                    dialogue.append(f"{speaker}: {text}")
                schema_data['example_dialogue'] = dialogue
            elif isinstance(schema_data.get('example_dialogue'), str):
                schema_data['example_dialogue'] = [line.strip() for line in schema_data['example_dialogue'].split('\n') if line.strip()]

            return jsonify(schema_data)
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Schema Parse Error: {e}")
            return jsonify({'error': 'Failed to parse generated schema'}), 500

    except Exception as e:
        logger.error(f"Unexpected error in generate_schema: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/use-generated-schema', methods=['POST'])
def use_generated_schema():
    """Route to save the generated schema as a new template"""
    try:
        schema_data = request.get_json()

        if not schema_data:
            return jsonify({'error': 'No schema data provided'}), 400

        # Convert all JSON fields to proper format
        persona_data = schema_data.get('persona', {})
        if isinstance(persona_data, str):
            try:
                persona_data = json.loads(persona_data)
            except json.JSONDecodeError:
                persona_data = {'description': persona_data}

        # Convert dialogue to proper format
        example_dialogue = schema_data.get('example_dialogue', [])
        if isinstance(example_dialogue, dict):
            dialogue_list = []
            for role, text in example_dialogue.items():
                dialogue_list.append(f"{role}: {text}")
            example_dialogue = dialogue_list
        elif isinstance(example_dialogue, str):
            example_dialogue = [line.strip() for line in example_dialogue.split('\n') if line.strip()]

        # Ensure rules and instructions are lists
        rules = schema_data.get('rules', [])
        if isinstance(rules, str):
            rules = [rules]

        instructions = schema_data.get('instructions', [])
        if isinstance(instructions, str):
            instructions = [instructions]

        # Create new message from schema with properly formatted data
        message = Message(
            name=f"Generated Template {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
            bio=schema_data.get('bio', ''),
            voice_style=schema_data.get('voice_style', ''),
            persona=persona_data,
            rules=rules,
            instructions=instructions,
            example_dialogue=example_dialogue,
            created_at=datetime.utcnow(),
            published=False,
            published_at=None
        )

        db.session.add(message)
        db.session.commit()

        return jsonify({
            'success': True,
            'redirect_url': url_for('preview_message', id=message.id)
        })

    except Exception as e:
        logger.error(f"Error saving generated schema: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/messages/<int:id>/export.<format>')
def export_message(id, format):
    """Export message in the specified format (xml or json)"""
    message = Message.query.get_or_404(id)

    if format == 'json':
        return jsonify(message.to_dict())
    elif format == 'xml':
        # Create XML representation
        xml_data = f'''<?xml version="1.0" encoding="UTF-8"?>
<message>
    <id>{message.id}</id>
    <name>{message.name}</name>
    <bio><![CDATA[{message.bio}]]></bio>
    <voice_style><![CDATA[{message.voice_style}]]></voice_style>
    <persona><![CDATA[{json.dumps(message.persona)}]]></persona>
    <rules><![CDATA[{json.dumps(message.rules)}]]></rules>
    <instructions><![CDATA[{json.dumps(message.instructions)}]]></instructions>
    <example_dialogue><![CDATA[{json.dumps(message.example_dialogue)}]]></example_dialogue>
    <published>{str(message.published).lower()}</published>
    <published_at>{message.published_at.isoformat() if message.published_at else ''}</published_at>
    <created_at>{message.created_at.isoformat()}</created_at>
    <updated_at>{message.updated_at.isoformat()}</updated_at>
</message>'''
        return Response(xml_data, mimetype='application/xml')
    else:
        return 'Unsupported format', 400


@app.route('/messages/<int:id>/publish', methods=['POST'])
def publish_message(id):
    """Route to publish a message"""
    try:
        message = Message.query.get_or_404(id)
        message.published = True
        message.published_at = datetime.utcnow()
        db.session.commit()
        flash('Message published successfully', 'success')
    except Exception as e:
        logger.error(f"Error publishing message: {e}")
        db.session.rollback()
        flash('Error publishing message', 'error')
    return redirect(url_for('preview_message', id=message.id))

@app.route('/messages/<int:id>/unpublish', methods=['POST'])
def unpublish_message(id):
    """Route to unpublish a message"""
    try:
        message = Message.query.get_or_404(id)
        message.published = False
        message.published_at = None
        db.session.commit()
        flash('Message unpublished successfully', 'success')
    except Exception as e:
        logger.error(f"Error unpublishing message: {e}")
        db.session.rollback()
        flash('Error unpublishing message', 'error')
    return redirect(url_for('preview_message', id=message.id))

@app.route('/messages/<int:id>/edit', methods=['GET', 'POST'])
def edit_message(id):
    """Route to edit an existing message"""
    message = Message.query.get_or_404(id)

    if request.method == 'POST':
        try:
            data = request.get_json()
            # Update message fields
            message.name = data.get('name', message.name)
            message.bio = data.get('bio', message.bio)
            message.voice_style = data.get('voice_style', message.voice_style)

            # Handle JSON fields
            if 'persona' in data:
                if isinstance(data['persona'], str):
                    message.persona = json.loads(data['persona'])
                else:
                    message.persona = data['persona']

            if 'rules' in data:
                message.rules = json.dumps(data['rules']) if isinstance(data['rules'], list) else data['rules']

            if 'instructions' in data:
                message.instructions = json.dumps(data['instructions']) if isinstance(data['instructions'], list) else data['instructions']

            if 'example_dialogue' in data:
                message.example_dialogue = json.dumps(data['example_dialogue']) if isinstance(data['example_dialogue'], list) else data['example_dialogue']

            message.updated_at = datetime.utcnow()
            db.session.commit()

            flash('Message updated successfully', 'success')
            return jsonify({'success': True, 'redirect_url': url_for('preview_message', id=message.id)})

        except Exception as e:
            logger.error(f"Error updating message: {e}")
            db.session.rollback()
            return jsonify({'error': str(e)}), 500

    return render_template('edit.html', message=message)

@app.route('/messages/<int:id>/copy', methods=['POST'])
def copy_message(id):
    """Route to create a copy of an existing message with version tracking"""
    try:
        source_message = Message.query.get_or_404(id)

        # Get the highest version number among copies
        max_version = db.session.query(db.func.max(Message.version_number)).filter(
            db.or_(
                Message.id == id,
                Message.original_id == id
            )
        ).scalar() or 1

        # Create a new message with copied content
        new_message = Message(
            name=f"{source_message.name} (Copy)",
            bio=source_message.bio,
            voice_style=source_message.voice_style,
            persona=source_message.persona.copy() if source_message.persona else {},
            rules=source_message.rules.copy() if isinstance(source_message.rules, list) else [],
            instructions=source_message.instructions.copy() if isinstance(source_message.instructions, list) else [],
            example_dialogue=source_message.example_dialogue.copy() if isinstance(source_message.example_dialogue, list) else [],
            created_at=datetime.utcnow(),
            published=False,
            published_at=None,
            # Version tracking information
            original_id=source_message.original_id or source_message.id,
            version_number=max_version + 1,
            version_note=f"Copied from version {source_message.version_number or 1}"
        )

        db.session.add(new_message)
        db.session.commit()
        flash('Message copied successfully', 'success')
        return redirect(url_for('preview_message', id=new_message.id))

    except Exception as e:
        logger.error(f"Error copying message: {e}")
        db.session.rollback()
        flash('Error copying message', 'error')
        return redirect(url_for('list_messages'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)