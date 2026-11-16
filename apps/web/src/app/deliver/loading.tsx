// While /deliver loads (e.g. a new city in the picker): the page's shape, not a blank.
export default function Loading() {
  const bar = "animate-pulse rounded-[12px] bg-porcelain";
  return (
    <div aria-busy="true" className="container-page pb-16 pt-8 md:pt-14">
      <div className="grid gap-8 lg:grid-cols-[1fr_520px] lg:gap-12">
        <div>
          <div className={`${bar} h-4 w-40`} />
          <div className={`${bar} mt-4 h-12 w-full max-w-[520px]`} />
          <div className={`${bar} mt-3 h-12 w-3/4 max-w-[420px]`} />
          <div className={`${bar} mt-6 h-6 w-full max-w-[520px]`} />
          <div className={`${bar} mt-8 h-[52px] w-48 rounded-full`} />
        </div>
        <div className={`${bar} aspect-[4/3] w-full rounded-[28px] md:rounded-[40px]`} />
      </div>
      <div className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[0, 1, 2, 3].map((i) => <div key={i} className={`${bar} h-48 rounded-[24px]`} />)}
      </div>
    </div>
  );
}
