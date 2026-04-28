export default function SideTag({ side }: { side: string }) {
  return side === '1'
    ? <span className="text-emerald-400 font-semibold">BUY</span>
    : <span className="text-red-400 font-semibold">SELL</span>
}
