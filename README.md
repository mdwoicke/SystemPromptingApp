# System Message Management Platform

A sophisticated web-based system message management platform designed for advanced XML template creation and collaborative messaging design. The application provides a powerful, flexible template builder that enables complex message structuring with granular content control and comprehensive persona management.

## Features

- Interactive template builder with drag-and-drop components
- Comprehensive persona management system
- XML and JSON export capabilities
- Message preview and publishing workflow
- Rich text editing for message components
- Version control and message history

## Technical Stack

- **Backend**: Flask (Python 3.11)
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Frontend**: Bootstrap 5 with jQuery for interactive features
- **XML Processing**: Native Python XML handling

## Installation

1. Clone the repository
2. Install dependencies:
```bash
pip install flask flask-sqlalchemy flask-login flask-wtf sqlalchemy psycopg2-binary email-validator
```

3. Set up environment variables:
```bash
export FLASK_SECRET_KEY="your-secret-key"
export DATABASE_URL="postgresql://user:password@localhost:5432/dbname"
```

4. Initialize the database:
```python
from app import app, db

with app.app_context():
    db.create_all()
```

## Usage Guide

### 1. Creating a New System Message

```python
# Example of creating a new system message via the API
from models import SystemMessage
from app import db

new_message = SystemMessage(
    name="Customer Service Bot",
    bio="Voice assistant for customer support",
    voice_style="Professional and friendly",
    persona={
        "age": "25-year-old professional",
        "occupation": "Customer Service Specialist",
        "attitude": "Helpful and patient",
        # ... other persona attributes
    },
    rules="Always be polite\nListen carefully\nProvide accurate information",
    instructions="Handle customer inquiries professionally",
    example_dialogue="Agent: Welcome to our support center\nCaller: I need help with my account"
)

db.session.add(new_message)
db.session.commit()
```

### 2. Using the Template Builder

The template builder provides a drag-and-drop interface for creating message templates. Components include:

- Bio
- Voice Style
- Persona
- Rules
- Instructions
- Example Dialogue

```html
<!-- Example of adding a new component in the builder -->
<div class="mb-3 component">
    <div class="card bg-dark border-secondary">
        <div class="card-header">
            <span>Bio</span>
        </div>
        <div class="card-body">
            <textarea class="form-control bg-dark text-light" 
                      rows="3" 
                      placeholder="Enter bio information..."></textarea>
        </div>
    </div>
</div>
```

### 3. Exporting Messages

Messages can be exported in both XML and JSON formats:

```python
# Example of XML export format
<system_message>
    <bio>Voice assistant for customer support</bio>
    <voice_style>Professional and friendly</voice_style>
    <persona>
        <age>25-year-old professional</age>
        <occupation>Customer Service Specialist</occupation>
        <attitude>Helpful and patient</attitude>
        <!-- ... other persona elements -->
    </persona>
    <important_rules>
        <rule>Always be polite</rule>
        <rule>Listen carefully</rule>
        <rule>Provide accurate information</rule>
    </important_rules>
    <instructions>
        Handle customer inquiries professionally
        <required_information>
            <item>Customer name</item>
            <item>Account number</item>
            <item>Issue description</item>
        </required_information>
    </instructions>
</system_message>
```

### 4. Database Schema

```python
class SystemMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    bio = db.Column(db.Text, nullable=False)
    voice_style = db.Column(db.Text, nullable=False)
    persona = db.Column(db.JSON, nullable=False)
    rules = db.Column(db.Text, nullable=False)
    instructions = db.Column(db.Text, nullable=False)
    example_dialogue = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    published = db.Column(db.Boolean, default=False)
    published_at = db.Column(db.DateTime, nullable=True)
```

## API Routes

### Message Management

```python
# Create new message
@app.route('/messages/create', methods=['POST'])
def create_message():
    # Handle message creation

# List all messages
@app.route('/messages')
def list_messages():
    # Return list of messages

# Preview specific message
@app.route('/messages/<int:id>')
def preview_message(id):
    # Show message preview

# Edit message
@app.route('/messages/<int:id>/edit', methods=['GET', 'POST'])
def edit_message(id):
    # Handle message editing

# Delete message
@app.route('/messages/<int:id>/delete')
def delete_message(id):
    # Handle message deletion

# Publish message
@app.route('/messages/<int:id>/publish')
def publish_message(id):
    # Handle message publishing
```

## Template Builder Interface

The template builder provides an interactive interface for creating message templates:

1. **Component Palette**: Drag-and-drop components from the left sidebar
2. **Preview Area**: Real-time preview of the template structure
3. **Export Options**: Export templates in XML or JSON format

```javascript
// Example of component initialization in template builder
$(function() {
    $(".draggable").draggable({
        helper: "clone",
        cursor: "move",
        revert: "invalid"
    });

    $("#preview").droppable({
        accept: ".draggable",
        drop: function(event, ui) {
            // Handle component drop
        }
    });
});
```

## Best Practices

1. **Persona Management**
   - Keep persona attributes consistent across templates
   - Use predefined fields for standardization
   - Include all required persona information

2. **Message Structure**
   - Follow XML schema guidelines
   - Maintain consistent formatting
   - Include required sections: bio, voice style, persona, rules, instructions

3. **Template Building**
   - Use drag-and-drop interface for component placement
   - Preview templates before saving
   - Validate all required fields

4. **Version Control**
   - Save incremental changes
   - Track message versions
   - Maintain publishing history

## Security Considerations

1. Input validation for all form submissions
2. SQL injection prevention through SQLAlchemy
3. XSS protection in template rendering
4. CSRF protection for forms
5. Secure database connections

## Contributing

1. Fork the repository
2. Create a feature branch
3. Submit a pull request with detailed description
4. Follow coding standards and documentation guidelines

## XML System Prompts vs Markdown

### Why XML is Superior for LLM System Prompts

1. **Enhanced Semantic Understanding**
   - XML tags act as explicit cognitive boundaries for LLMs
   - Hierarchical structure mirrors natural language processing patterns
   - Tags provide clear contextual signals that improve prompt interpretation
   - Reduces hallucination by constraining responses within defined structures

2. **Superior Context Management**
   - Nested XML elements maintain relationships between concepts
   - Context inheritance follows logical parent-child relationships
   - Scoped information prevents context bleed between sections
   - Enables complex multi-turn conversations without losing context

3. **Precise Control Over LLM Behavior**
   - Tag attributes provide fine-grained control over LLM responses
   - Explicit role declarations improve consistency in persona maintenance
   - Validation constraints prevent off-prompt responses
   - Structure enforces compliance with desired output formats

4. **Technical Advantages**
   - Self-documenting structure improves prompt maintenance
   - Built-in schema validation ensures prompt integrity
   - Easy transformation to other formats (JSON, YAML)
   - Superior parsing capabilities for automated processing

5. **Real-world Evidence**
   - Consistently higher accuracy in maintaining context
   - Reduced token usage through structured prompting
   - More predictable and reliable LLM responses
   - Better handling of complex, multi-part instructions

Unlike Markdown's loose formatting, XML provides a robust framework that actively guides LLM behavior while maintaining strict boundaries between different prompt components. This results in more reliable, consistent, and controllable AI responses.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
