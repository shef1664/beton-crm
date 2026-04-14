/**
 * Скрипт для создания скриншотов всех 5 лендингов
 * Desktop + Mobile версии
 * Сохраняет в temporary-screenshots/
 */

const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

const variants = [
  { name: 'landing-kdm', label: 'KDM - Монолит Групп' },
  { name: 'landing-vedro', label: 'Vedro - БетонСтрой Логистика' },
  { name: 'landing-speed', label: 'Speed - Гранитон' },
  { name: 'landing-trust', label: 'Trust - Цементум' },
  { name: 'landing-calc', label: 'Calc - ТрансМикс' }
];

const devices = [
  { name: 'desktop', width: 1920, height: 1080 },
  { name: 'mobile', width: 375, height: 812 }
];

const outputDir = path.join(__dirname, 'temporary-screenshots');

// Создаём папку если нет
if (!fs.existsSync(outputDir)) {
  fs.mkdirSync(outputDir, { recursive: true });
}

async function takeScreenshot(browser, variant, device) {
  const page = await browser.newPage();
  
  // Устанавливаем размер
  await page.setViewport({ width: device.width, height: device.height });
  
  // Формируем путь к файлу
  const filePath = path.join(outputDir, `${variant.name}-${device.name}.png`);
  const fileURL = `file:///${path.resolve(__dirname, 'variants', variant.name, 'index.html')}`;
  
  try {
    console.log(`📸 ${variant.label} (${device.name})...`);
    
    // Открываем страницу
    await page.goto(fileURL, { waitUntil: 'networkidle0', timeout: 10000 });
    
    // Ждём загрузки шрифтов и анимаций
    await new Promise(r => setTimeout(r, 1000));
    
    // Делаем скриншот
    await page.screenshot({ 
      path: filePath, 
      fullPage: true,
      type: 'png'
    });
    
    console.log(`✅ Сохранено: ${filePath}`);
  } catch (err) {
    console.error(`❌ Ошибка для ${variant.label} (${device.name}):`, err.message);
  } finally {
    await page.close();
  }
}

async function main() {
  console.log('🚀 Запуск скриншотов...\n');
  
  const browser = await puppeteer.launch({
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });
  
  let total = variants.length * devices.length;
  let done = 0;
  
  for (const variant of variants) {
    for (const device of devices) {
      await takeScreenshot(browser, variant, device);
      done++;
      console.log(`   Прогресс: ${done}/${total}\n`);
    }
  }
  
  await browser.close();
  
  console.log('\n✅ ВСЕ СКРИНШОТЫ СОЗДАНЫ!');
  console.log(`📁 Папка: ${outputDir}`);
  console.log('\nФайлы:');
  variants.forEach(v => {
    devices.forEach(d => {
      console.log(`  - ${v.name}-${d.name}.png`);
    });
  });
}

main().catch(console.error);
