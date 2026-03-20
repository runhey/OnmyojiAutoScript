# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pydantic import BaseModel

from module.logger import logger
from module.server.tool import AnnotatorError, annotator_manager

tool_app = APIRouter(
    prefix="/tool",
    tags=["tool"],
)


class EmulatorStartBody(BaseModel):
    session_id: str
    config_name: str
    frame_rate: int = 2


class SessionBody(BaseModel):
    session_id: str


class RuleSaveBody(BaseModel):
    session_id: str
    task_name: str
    json_relpath: str
    rule_type: str
    rules: list[dict[str, Any]]
    list_meta: dict[str, Any] | None = None


class UploadImageItem(BaseModel):
    name: str
    content_base64: str


class UploadImagesBody(BaseModel):
    session_id: str
    images: list[UploadImageItem]


class BatchDeleteImagesBody(BaseModel):
    session_id: str
    image_ids: list[str]


class CropSaveBody(BaseModel):
    session_id: str
    image_id: str
    task_name: str
    json_relpath: str
    image_name: str
    roi: str


class RuleImageDeleteBody(BaseModel):
    task_name: str
    json_relpath: str
    image_name: str


class RuleFileCreateBody(BaseModel):
    dir_path: str
    file_name: str


class RuleFileDeleteBody(BaseModel):
    dir_path: str
    file_name: str


class RuleTestBody(BaseModel):
    session_id: str
    image_id: str
    task_name: str
    json_relpath: str
    rule_type: str
    rule: dict[str, Any]
    list_meta: dict[str, Any] | None = None

def _raise_annotator_error(e: AnnotatorError) -> None:
    raise HTTPException(
        status_code=e.status_code,
        detail={"code": e.code, "message": e.message},
    )


def _close_session_safely(session_id: str, reason: str) -> dict[str, Any]:
    return annotator_manager.close_session(session_id, reason=reason, raise_if_missing=False)


@tool_app.get('/annotator')
async def tool_annotator_page():
    page = annotator_manager.index_file()
    if not page.exists():
        raise HTTPException(status_code=404, detail={"code": "page_not_found", "message": "标注页面不存在"})
    return FileResponse(page)


@tool_app.post('/annotator/api/session')
async def annotator_create_session():
    session = annotator_manager.create_session()
    return {"code": "ok", "session": session}


@tool_app.get('/annotator/api/session/{session_id}')
async def annotator_get_session(session_id: str):
    try:
        session = annotator_manager.get_session_snapshot(session_id)
        return {"code": "ok", "session": session}
    except AnnotatorError as e:
        _raise_annotator_error(e)




@tool_app.delete('/annotator/api/session/{session_id}')
async def annotator_close_session(session_id: str, reason: str = "client_close"):
    try:
        result = _close_session_safely(session_id, f"api:{reason}")
        return {"code": "ok", **result}
    except AnnotatorError as e:
        _raise_annotator_error(e)


@tool_app.post('/annotator/api/session/{session_id}/close')
async def annotator_close_session_beacon(session_id: str, reason: str = "pagehide"):
    try:
        result = _close_session_safely(session_id, f"beacon:{reason}")
        return {"code": "ok", **result}
    except AnnotatorError as e:
        _raise_annotator_error(e)

@tool_app.post('/annotator/api/images/upload')
async def annotator_upload_images(data: UploadImagesBody):
    try:
        images = annotator_manager.save_uploaded_images_base64(
            data.session_id,
            [item.dict() for item in data.images],
        )
        return {"code": "ok", "images": images}
    except AnnotatorError as e:
        _raise_annotator_error(e)


@tool_app.get('/annotator/api/images')
async def annotator_list_images(session_id: str):
    try:
        images = annotator_manager.list_images(session_id)
        return {"code": "ok", "images": images}
    except AnnotatorError as e:
        _raise_annotator_error(e)


@tool_app.get('/annotator/api/images/{session_id}/{image_id}')
async def annotator_image_file(session_id: str, image_id: str):
    try:
        image = annotator_manager.get_image_file(session_id, image_id)
        return FileResponse(image)
    except AnnotatorError as e:
        _raise_annotator_error(e)


@tool_app.delete('/annotator/api/images/{session_id}/{image_id}')
async def annotator_delete_image(session_id: str, image_id: str):
    try:
        session = annotator_manager.delete_image(session_id, image_id)
        return {"code": "ok", "session": session}
    except AnnotatorError as e:
        _raise_annotator_error(e)


@tool_app.post('/annotator/api/images/delete-batch')
async def annotator_delete_batch_images(data: BatchDeleteImagesBody):
    try:
        result = annotator_manager.delete_images(data.session_id, data.image_ids)
        return {"code": "ok", **result}
    except AnnotatorError as e:
        _raise_annotator_error(e)


@tool_app.post('/annotator/api/images/clear')
async def annotator_clear_images(data: SessionBody):
    try:
        result = annotator_manager.clear_images(data.session_id)
        return {"code": "ok", **result}
    except AnnotatorError as e:
        _raise_annotator_error(e)


@tool_app.get('/annotator/api/configs')
async def annotator_configs():
    configs = annotator_manager.list_configs()
    return {"code": "ok", "configs": configs}


@tool_app.get('/annotator/api/tasks')
async def annotator_tasks():
    tasks = annotator_manager.list_task_names()
    return {"code": "ok", "tasks": tasks}


@tool_app.get('/annotator/api/tasks/{task_name}/json')
async def annotator_task_json_files(task_name: str):
    try:
        files = annotator_manager.list_task_json_files(task_name)
        return {"code": "ok", "json_files": files}
    except AnnotatorError as e:
        _raise_annotator_error(e)


@tool_app.get('/annotator/api/rules/load')
async def annotator_load_rules(task_name: str, json_relpath: str):
    try:
        data = annotator_manager.load_rule_file(task_name, json_relpath)
        return {"code": "ok", **data}
    except AnnotatorError as e:
        _raise_annotator_error(e)


@tool_app.get('/annotator/api/rules/source')
async def annotator_rule_source(dir_path: str = ""):
    try:
        data = annotator_manager.list_rule_source(dir_path)
        return {"code": "ok", **data}
    except AnnotatorError as e:
        _raise_annotator_error(e)


@tool_app.post('/annotator/api/rules/source/create')
async def annotator_rule_source_create(data: RuleFileCreateBody):
    try:
        result = annotator_manager.create_rule_json(data.dir_path, data.file_name)
        return {"code": "ok", **result}
    except AnnotatorError as e:
        _raise_annotator_error(e)


@tool_app.post('/annotator/api/rules/source/delete')
async def annotator_rule_source_delete(data: RuleFileDeleteBody):
    try:
        result = annotator_manager.delete_rule_json(data.dir_path, data.file_name)
        return {"code": "ok", **result}
    except AnnotatorError as e:
        _raise_annotator_error(e)


@tool_app.get('/annotator/api/rules/image-preview')
async def annotator_rule_image_preview(task_name: str, json_relpath: str, image_name: str):
    try:
        image = annotator_manager.get_rule_image_file(task_name, json_relpath, image_name)
        return FileResponse(image)
    except AnnotatorError as e:
        _raise_annotator_error(e)


@tool_app.post('/annotator/api/rules/image/delete')
async def annotator_rule_image_delete(data: RuleImageDeleteBody):
    try:
        result = annotator_manager.delete_rule_image(data.task_name, data.json_relpath, data.image_name)
        return {"code": "ok", **result}
    except AnnotatorError as e:
        _raise_annotator_error(e)


@tool_app.post('/annotator/api/emulator/start')
async def annotator_start_emulator(data: EmulatorStartBody):
    try:
        status = annotator_manager.start_emulator(data.session_id, data.config_name, data.frame_rate)
        return {"code": "ok", "emulator": status}
    except AnnotatorError as e:
        _raise_annotator_error(e)


@tool_app.post('/annotator/api/emulator/stop')
async def annotator_stop_emulator(data: SessionBody):
    try:
        status = annotator_manager.stop_emulator(data.session_id)
        return {"code": "ok", "emulator": status}
    except AnnotatorError as e:
        _raise_annotator_error(e)


@tool_app.get('/annotator/api/emulator/status')
async def annotator_emulator_status(session_id: str):
    try:
        status = annotator_manager.emulator_status(session_id)
        return {"code": "ok", "emulator": status}
    except AnnotatorError as e:
        _raise_annotator_error(e)


@tool_app.post('/annotator/api/emulator/capture')
async def annotator_capture_frame(data: SessionBody):
    try:
        image = annotator_manager.capture_from_emulator(data.session_id)
        return {"code": "ok", "image": image}
    except AnnotatorError as e:
        _raise_annotator_error(e)


@tool_app.post('/annotator/api/rules/test')
async def annotator_test_rule(data: RuleTestBody):
    try:
        result = annotator_manager.test_rule(
            session_id=data.session_id,
            image_id=data.image_id,
            task_name=data.task_name,
            json_relpath=data.json_relpath,
            rule_type=data.rule_type,
            rule=data.rule,
            list_meta=data.list_meta,
        )
        return {"code": "ok", "result": result}
    except AnnotatorError as e:
        _raise_annotator_error(e)


@tool_app.post('/annotator/api/rules/save')
async def annotator_save_rules(data: RuleSaveBody):
    try:
        result = annotator_manager.save_rules_and_generate(
            session_id=data.session_id,
            task_name=data.task_name,
            json_relpath=data.json_relpath,
            rule_type=data.rule_type,
            rules=data.rules,
            list_meta=data.list_meta,
        )
        code = "ok" if result.get("generate_status") == "success" else "partial_success"
        return {"code": code, **result}
    except AnnotatorError as e:
        _raise_annotator_error(e)


@tool_app.post('/annotator/api/images/crop-save')
async def annotator_crop_save(data: CropSaveBody):
    try:
        result = annotator_manager.save_cropped_image(
            session_id=data.session_id,
            image_id=data.image_id,
            task_name=data.task_name,
            json_relpath=data.json_relpath,
            image_name=data.image_name,
            roi=data.roi,
        )
        return {"code": "ok", **result}
    except AnnotatorError as e:
        _raise_annotator_error(e)


@tool_app.websocket('/annotator/ws/{session_id}')
async def annotator_frame_ws(websocket: WebSocket, session_id: str):
    await websocket.accept()
    try:
        annotator_manager.get_session_snapshot(session_id)
        while True:
            frame = annotator_manager.latest_emulator_frame(session_id)
            if frame:
                await websocket.send_bytes(frame)
                continue

            status = annotator_manager.emulator_status(session_id)
            if status.get("state") == "error":
                await websocket.send_json(
                    {
                        "event": "error",
                        "code": "emulator_error",
                        "message": status.get("error", "unknown"),
                    }
                )
                await websocket.close(code=1011)
                break

            await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        logger.info(f"[annotator] ws disconnect, session={session_id}")
    except AnnotatorError as e:
        if e.code != "invalid_session":
            logger.warning(f"[annotator] ws annotator error, session={session_id}, code={e.code}")
        try:
            await websocket.send_json({"event": "error", "code": e.code, "message": e.message})
        except Exception:
            pass
        try:
            await websocket.close(code=1008)
        except Exception:
            pass
    except Exception as e:
        message = str(e).strip().lower()
        if e.__class__.__name__ == "ClientDisconnected" or "disconnected" in message:
            logger.info(f"[annotator] ws client disconnected during send, session={session_id}")
        else:
            logger.exception(f"[annotator] ws failed, session={session_id}")
        try:
            await websocket.close(code=1011)
        except Exception:
            pass


