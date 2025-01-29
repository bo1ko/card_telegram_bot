from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession


async def orm_create(session: AsyncSession, model: object, data: dict):
    obj = model(**data)
    session.add(obj)
    await session.commit()


async def orm_read(session: AsyncSession, model: object, pk: int = None):
    try:
        if pk:
            result = await session.execute(select(model).where(model.pk == pk))
            return result.scalar()
        else:
            result = await session.execute(select(model))
            return result.scalars().all()
    except Exception as e:
        print(e)
        return False


async def orm_update(session: AsyncSession, model: object, pk: int, data: dict):
    await session.execute(update(model).where(model.pk == pk).values(**data))
    return await session.commit()


async def orm_delete(session: AsyncSession, model: object, pk: int):
    await session.execute(delete(model).where(model.pk == pk))
    return await session.commit()
