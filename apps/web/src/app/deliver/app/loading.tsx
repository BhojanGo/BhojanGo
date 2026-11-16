// While /deliver/app loads: the page's shape (heading, the store box), not a blank.
export default function Loading() {
  const bar = "animate-pulse rounded-[12px] bg-porcelain";
  return (
    <div aria-busy="true" className="mx-auto w-full max-w-[1200px] px-4 py-12 md:px-8 md:py-16 lg:px-12">
      <div className="max-w-[640px]">
        <div className={`${bar} h-4 w-40`} />
        <div className={`${bar} mt-4 h-10 w-3/4`} />
        <div className={`${bar} mt-4 h-6 w-full`} />
        <div className={`${bar} mt-8 h-36 w-full rounded-[20px]`} />
      </div>
    </div>
  );
}
