import { useEffect, useMemo, useRef, useState } from "react";
import throttle from "lodash/throttle";

export function useThrottle<T>(value: T, wait = 250): T {
  const [throttled, setThrottled] = useState(value);
  const setterRef = useRef(setThrottled);
  setterRef.current = setThrottled;

  const setter = useMemo(
    () => throttle((next: T) => setterRef.current(next), wait, { leading: true, trailing: true }),
    [wait]
  );

  useEffect(() => {
    setter(value);
    return () => setter.cancel();
  }, [value, setter]);

  return throttled;
}
