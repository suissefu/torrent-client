from rich.live import Live
from rich.table import Table
from app import app
from peer import PeerState
from piece import PieceState
import asyncio

def build_dashboard():
    table = Table(title = "Bittorrent Status")
    table.add_column("Metric")
    table.add_column("Value")
    table.add_row("Active: ", ", ".join([f"{peer.ip}:{peer.port}" for peer in app.peer_pool.get_all(PeerState.ACTIVE)]))
    table.add_row("   ", "   ")
    table.add_row("Queued: ", ", ".join([f"{peer.ip}:{peer.port}" for peer in app.peer_pool.get_all(PeerState.QUEUED)]))
    table.add_row("   ", "   ")
    table.add_row("Failed: ", ", ".join([f"{peer.ip}:{peer.port}" for peer in app.peer_pool.get_all(PeerState.FAILED)]))
    table.add_row("   ", "   ")
    table.add_row("Banned: ", ", ".join([f"{peer.ip}:{peer.port}" for peer in app.peer_pool.get_all(PeerState.BANNED)]))
    table.add_row("   ", "   ")
    table.add_row("Connecting: ", ", ".join([f"{peer.ip}:{peer.port}" for peer in app.peer_pool.get_all(PeerState.CONNECTING)]))
    table.add_row("   ", "   ")
    table.add_row("Fail Count (Queued): ", ", ".join([f"{peer.ip}:{peer.port} | {peer._fail_count}" for peer in app.peer_pool.get_all(PeerState.QUEUED)]))
    table.add_row("   ", "   ")
    table.add_row("Fail Count: (Connecting)", ", ".join([f"{peer.ip}:{peer.port} | {peer._fail_count}" for peer in app.peer_pool.get_all(PeerState.CONNECTING)]))
    piece_completed = len(app.bitfield.get_all(1))
    piece_total = len(app.bitfield)
    table.add_row(
        "Piece Completed | Piece Total :", 
        f"{piece_completed} | {piece_total}"   
    )
    table.add_row("Download Status: ", f"{piece_completed / piece_total:.2%}")
    return table

async def dashboard_loop():
    with Live(build_dashboard(), refresh_per_second = 2) as live:
        while True:
            live.update(build_dashboard())
            await asyncio.sleep(0.5)