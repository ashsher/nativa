"""Add recommended_content table with seed data

Revision ID: 0002
Revises: None (standalone; set down_revision='0001' when 0001 migration exists)
Create Date: 2024-01-01 00:00:00

Creates the recommended_content table and seeds it with 20 videos and
20 articles for the /api/content/recommended endpoint.
"""

# Alembic revision chain identifiers.
revision = '0002'
# down_revision = None makes this a standalone branch-head migration.
# Change to '0001' if the 0001 migration is present in the same project.
down_revision = None
branch_labels = None
depends_on = None

from alembic import op           # Alembic DDL operation helpers
import sqlalchemy as sa           # SQLAlchemy type classes for column definitions
from sqlalchemy import text       # text() wraps raw SQL strings for op.execute()


def upgrade():
    """
    Create the recommended_content table and seed it with 40 rows:
      - 20 beginner YouTube videos (TED, Kurzgesagt, BBC, NatGeo, cooking, travel)
      - 20 beginner articles (Simple Wikipedia, BBC Learning English, NatGeo, Smithsonian)
    """
    # Create the recommended_content table with five columns.
    op.create_table(
        'recommended_content',
        # Auto-incrementing surrogate primary key.
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        # 'video' or 'article' — used by the frontend to choose the card icon.
        sa.Column('content_type', sa.String(10), nullable=False),
        # Full URL to the YouTube video or article web page.
        sa.Column('url', sa.Text, nullable=False),
        # Human-readable English title shown in the recommended content list.
        sa.Column('title', sa.String(200), nullable=False),
        # Thematic topic tag for optional client-side filtering.
        sa.Column('topic', sa.String(100)),
        # Difficulty level; all seed rows are 'beginner'.
        sa.Column('difficulty', sa.String(20), default='beginner'),
    )

    # ── Seed: 20 beginner YouTube videos ──────────────────────────────────────
    # Sources: TED-Ed, Kurzgesagt, BBC Learning English, National Geographic,
    # cooking channels, and city travel vlogs — all use clear accessible English.
    op.execute(text("""
    INSERT INTO recommended_content (content_type, url, title, topic, difficulty) VALUES
    ('video','https://www.youtube.com/watch?v=ArABhwAdaOA','Do schools kill creativity? | Sir Ken Robinson','education','beginner'),
    ('video','https://www.youtube.com/watch?v=1MgEkmJdXBs','The linguistic genius of babies | Patricia Kuhl','language','beginner'),
    ('video','https://www.youtube.com/watch?v=Unzc731iCUY','How to speak so that people want to listen','communication','beginner'),
    ('video','https://www.youtube.com/watch?v=eIho2S0ZahI','BBC Learning English: 6 Minute English - Sleep','health','beginner'),
    ('video','https://www.youtube.com/watch?v=pT6mS6Dq0HQ','BBC Learning English: Greetings and Introductions','basics','beginner'),
    ('video','https://www.youtube.com/watch?v=LnUTMOBCxq0','Kurzgesagt - Optimistic Nihilism','philosophy','beginner'),
    ('video','https://www.youtube.com/watch?v=0HLjuVyIIrs','Kurzgesagt - What Is Intelligence?','science','beginner'),
    ('video','https://www.youtube.com/watch?v=NkFovA8ExJc','Kurzgesagt - Loneliness','wellness','beginner'),
    ('video','https://www.youtube.com/watch?v=wEV90m7iNKk','How to Make Perfect Pasta','cooking','beginner'),
    ('video','https://www.youtube.com/watch?v=HRbhrxuSMsU','Gordon Ramsay: How to Cook the Perfect Omelette','cooking','beginner'),
    ('video','https://www.youtube.com/watch?v=dY5PxCiM0DY','Easy Chicken Curry Recipe','cooking','beginner'),
    ('video','https://www.youtube.com/watch?v=GcLIABnBvJw','Japan Travel Vlog Tokyo','travel','beginner'),
    ('video','https://www.youtube.com/watch?v=5O-oVeJEmMU','London City Guide Travel Vlog','travel','beginner'),
    ('video','https://www.youtube.com/watch?v=cN7wUGiIBbY','New York City Travel Guide','travel','beginner'),
    ('video','https://www.youtube.com/watch?v=IXxZRZxafEQ','National Geographic: Ocean Wonders','nature','beginner'),
    ('video','https://www.youtube.com/watch?v=wh0UNICKE_4','National Geographic: Wild Animals of Africa','nature','beginner'),
    ('video','https://www.youtube.com/watch?v=tgbNymZ7vqY','National Geographic: Space Exploration','science','beginner'),
    ('video','https://www.youtube.com/watch?v=qYR_oNsoqs4','BBC Learning English: Business English Vocabulary','business','beginner'),
    ('video','https://www.youtube.com/watch?v=FLGCGc7sAhg','TED-Ed: How does the immune system work?','science','beginner'),
    ('video','https://www.youtube.com/watch?v=zQQD6mCLZ_Y','TED-Ed: What makes a good life?','philosophy','beginner')
    """))

    # ── Seed: 20 beginner articles ─────────────────────────────────────────────
    # Sources: Simple Wikipedia (plain language), BBC Learning English, National
    # Geographic, and Smithsonian Magazine — all appropriate for B1-B2 learners.
    op.execute(text("""
    INSERT INTO recommended_content (content_type, url, title, topic, difficulty) VALUES
    ('article','https://simple.wikipedia.org/wiki/Artificial_intelligence','Artificial Intelligence - Simple Wikipedia','technology','beginner'),
    ('article','https://simple.wikipedia.org/wiki/Climate_change','Climate Change - Simple Wikipedia','environment','beginner'),
    ('article','https://simple.wikipedia.org/wiki/Internet','The Internet - Simple Wikipedia','technology','beginner'),
    ('article','https://simple.wikipedia.org/wiki/Solar_System','Solar System - Simple Wikipedia','science','beginner'),
    ('article','https://simple.wikipedia.org/wiki/Human_body','Human Body - Simple Wikipedia','health','beginner'),
    ('article','https://www.bbc.co.uk/learningenglish/english/features/6-minute-english','BBC 6 Minute English','various','beginner'),
    ('article','https://www.bbc.co.uk/learningenglish/english/features/lingohack','BBC Lingohack: News Vocabulary','news','beginner'),
    ('article','https://www.bbc.co.uk/learningenglish/english/features/real-easy-english','BBC Real Easy English','basics','beginner'),
    ('article','https://www.bbc.co.uk/learningenglish/english/features/learners-questions','BBC Learners Questions','grammar','beginner'),
    ('article','https://www.bbc.co.uk/learningenglish/english/features/the-english-we-speak','BBC The English We Speak','vocabulary','beginner'),
    ('article','https://www.nationalgeographic.com/animals/article/coral-reefs','Coral Reefs - National Geographic','nature','beginner'),
    ('article','https://www.nationalgeographic.com/environment/article/global-warming','Global Warming Facts','environment','beginner'),
    ('article','https://www.nationalgeographic.com/animals/article/wolves','Wolves - National Geographic','nature','beginner'),
    ('article','https://www.nationalgeographic.com/science/article/space-exploration','Space Exploration History','science','beginner'),
    ('article','https://www.nationalgeographic.com/culture/article/ancient-egypt','Ancient Egypt','history','beginner'),
    ('article','https://www.smithsonianmag.com/arts-culture/history-of-music','A Brief History of Music','culture','beginner'),
    ('article','https://www.smithsonianmag.com/arts-culture/how-languages-evolve','How Languages Evolve','language','beginner'),
    ('article','https://www.smithsonianmag.com/science-nature/history-of-coffee','The History of Coffee','culture','beginner'),
    ('article','https://www.smithsonianmag.com/arts-culture/world-food-traditions','World Food Traditions','culture','beginner'),
    ('article','https://www.smithsonianmag.com/science-nature/ocean-facts','Amazing Ocean Facts','science','beginner')
    """))


def downgrade():
    """Drop the recommended_content table. All seeded data will be lost."""
    op.drop_table('recommended_content')
