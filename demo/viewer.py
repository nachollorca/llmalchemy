"""Database viewer page — shows tables marked with __show__ = True."""

import streamlit as st
from fixtures import Base

st.header(":material/database: Database Viewer")

session = st.session_state.session

# Discover visible tables
visible: list[tuple[str, type[Base]]] = []
for cls in Base.__subclasses__():
    if getattr(cls, "__show__", False):
        name = cls.__tablename__ if hasattr(cls, "__tablename__") else cls.__table__.name
        visible.append((name, cls))

if not visible:
    st.info("No visible tables defined in the schema.")
    st.stop()

table_names = [name for name, _ in visible]
selected = st.selectbox("Table", table_names)

cls = dict(visible)[selected]
columns = [c.key for c in cls.__table__.columns]
rows = session.query(cls).all()

if not rows:
    st.info(f"*{selected}* is empty.")
else:
    data = [{col: getattr(row, col) for col in columns} for row in rows]
    st.dataframe(data, width="stretch")
